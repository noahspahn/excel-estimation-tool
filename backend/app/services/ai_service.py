import os
from typing import Dict, Any, List, Optional


class AIService:
    """Thin wrapper around OpenAI to generate report narratives."""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        # Lazy import in methods to avoid hard dependency during boot

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate_narrative(
        self,
        estimation_data: Dict[str, Any],
        input_summary: Dict[str, Any],
        sections: Optional[List[str]] = None,
        tone: str = "professional",
        model: str = "gpt-4o-mini",
    ) -> Dict[str, str]:
        if not self.is_configured():
            raise RuntimeError("OPENAI_API_KEY not configured")

        # Try OpenAI SDK v1 first, then fall back to legacy 0.x if present
        client = None
        client_mode = None  # "v1" or "v0"
        v1_import_error = None
        try:
            from openai import OpenAI  # type: ignore

            client = OpenAI(api_key=self.api_key)
            client_mode = "v1"
        except Exception as e:
            v1_import_error = e
            try:
                import openai  # type: ignore

                openai.api_key = self.api_key
                client = openai
                client_mode = "v0"
            except Exception as legacy_e:
                installed_version = None
                try:
                    import openai as maybe_openai  # type: ignore

                    installed_version = getattr(maybe_openai, "__version__", None)
                except Exception:
                    pass

                details = [
                    "OpenAI SDK not available.",
                    "Install or upgrade with: pip install -U openai",
                ]
                if installed_version:
                    details.append(f"Detected openai version: {installed_version}")
                details.append(f"v1 import error: {v1_import_error}")
                details.append(f"v0 import error: {legacy_e}")
                raise RuntimeError("; ".join(details))

        if sections is None:
            sections = ["executive_summary", "assumptions", "risks", "recommendations"]

        result = estimation_data.get("estimation_result", {})

        # Prepare a compact, structured context for the model
        context = {
            "summary": {
                "total_labor_hours": round(float(result.get("total_labor_hours", 0)), 2),
                "total_labor_cost": round(float(result.get("total_labor_cost", 0)), 2),
                "risk_reserve": round(float(result.get("risk_reserve", 0)), 2),
                "overhead_cost": round(float(result.get("overhead_cost", 0)), 2),
                "total_cost": round(float(result.get("total_cost", 0)), 2),
                "effective_hourly_rate": round(float(result.get("effective_hourly_rate", 0)), 2),
                "complexity": input_summary.get("complexity"),
                "module_count": input_summary.get("module_count"),
            },
            "modules": [
                {
                    "name": m.get("module_name"),
                    "focus_area": m.get("focus_area"),
                    "hours": round(float(m.get("hours", 0)), 1),
                    "cost": round(float(m.get("cost", 0)), 2),
                }
                for m in (result.get("breakdown_by_module", {}) or {}).values()
            ],
            "roles": [
                {
                    "role": r.get("role_name"),
                    "hours": round(float(r.get("hours", 0)), 1),
                    "rate": round(float(r.get("effective_rate", 0)), 2),
                    "cost": round(float(r.get("cost", 0)), 2),
                }
                for r in (result.get("breakdown_by_role", {}) or {}).values()
            ],
        }

        sys_prompt = (
            "You are a consulting engagement manager. Write concise, clear, and client-ready "
            "narratives for an estimation report. Use the provided data faithfully. Avoid exaggeration."
        )

        user_prompt = (
            "Generate the following sections as short paragraphs (3-6 sentences each).\n"
            f"Tone: {tone}.\n"
            f"Sections: {', '.join(sections)}.\n"
            "Return a JSON object with keys exactly matching the requested section names.\n"
            "Context follows as JSON:\n" + str(context)
        )

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Call appropriate API depending on SDK mode
        if client_mode == "v1":
            try:
                completion = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.5,
                )
                content = completion.choices[0].message.content or "{}"
            except Exception:
                return self._offline_narrative(context, sections, tone)
        else:
            try:
                completion = client.ChatCompletion.create(
                    model=model,
                    messages=messages,
                    temperature=0.5,
                )
                content = completion["choices"][0]["message"]["content"] or "{}"
            except Exception:
                return self._offline_narrative(context, sections, tone)

        # Best-effort parse into a dict; if parsing fails, wrap as a single section
        try:
            import json

            data = json.loads(content)
            if isinstance(data, dict):
                return {k: str(v) for k, v in data.items()}
        except Exception:
            pass

        # Fallback: single blob under 'executive_summary' if JSON parse fails
        return {sections[0] if sections else "executive_summary": content}


    def _offline_narrative(
        self,
        context: Dict[str, Any],
        sections: List[str],
        tone: str,
    ) -> Dict[str, str]:
        secs = sections or ["executive_summary", "assumptions", "risks", "recommendations"]
        summary = context.get("summary", {})
        modules = context.get("modules", [])
        roles = context.get("roles", [])

        total_hours = summary.get("total_labor_hours") or 0
        total_cost = summary.get("total_cost") or 0
        risk_reserve = summary.get("risk_reserve") or 0
        overhead_cost = summary.get("overhead_cost") or 0
        eff_rate = summary.get("effective_hourly_rate") or 0
        complexity = summary.get("complexity") or "M"
        mod_count = summary.get("module_count") or len(modules)

        module_names = ", ".join([m.get("name") or "module" for m in modules]) or "selected modules"
        top_roles = ", ".join([r.get("role") or "role" for r in roles[:3]])

        text: Dict[str, str] = {}

        if "executive_summary" in secs:
            text["executive_summary"] = (
                f"This estimate covers {mod_count} {('module' if mod_count==1 else 'modules')} "
                f"with a {complexity} complexity profile. The projected effort is approximately "
                f"{total_hours:.0f} labor hours, with a total cost of ${total_cost:,.2f}. "
                f"The figure includes a risk reserve of ${risk_reserve:,.2f} and overhead of ${overhead_cost:,.2f}. "
                f"The effective blended rate is about ${eff_rate:,.2f} per hour."
            )

        if "assumptions" in secs:
            text["assumptions"] = (
                f"Estimates assume a typical staffing mix ({top_roles or 'multi‑disciplinary team'}) and standard project cadence. "
                f"Module sequencing accounts for prerequisites and reasonable dependency alignment. "
                f"Stakeholder access and decision cadence are consistent with the proposed schedule."
            )

        if "risks" in secs:
            text["risks"] = (
                f"Primary risks include scope growth and integration unknowns that could extend effort beyond the baseline {total_hours:.0f} hours. "
                f"Multi‑module dependencies ({module_names}) may impact sequencing and throughput. "
                f"The allocated risk reserve of ${risk_reserve:,.2f} is intended to buffer typical variance."
            )

        if "recommendations" in secs:
            text["recommendations"] = (
                "Begin with a short planning sprint to refine scope and confirm interfaces. "
                "Sequence delivery to realize early value while de‑risking complex integrations. "
                "Review staffing against milestones and adjust to maintain schedule confidence."
            )

        return text
