import os
import json
from typing import Dict, Any, List, Optional, Tuple


class SubtaskAIError(RuntimeError):
    def __init__(self, message: str, raw_content: Optional[str] = None):
        super().__init__(message)
        self.raw_content = raw_content


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

        context = self._build_narrative_context(estimation_data, input_summary)

        sys_prompt = (
            "You are a consulting engagement manager. Write concise, clear, and client-ready narratives "
            "for an estimation report. Use the provided data faithfully. Avoid exaggeration. "
            "Return ONLY valid JSON (no code fences, no extra text) with keys matching the requested sections."
        )

        user_payload = {
            "tone": tone,
            "sections": sections,
            "context": context,
        }
        user_prompt = json.dumps(user_payload)

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
                    temperature=0.3,
                )
                content = completion.choices[0].message.content or "{}"
            except Exception:
                return self._offline_narrative(context, sections, tone)
        else:
            try:
                completion = client.ChatCompletion.create(
                    model=model,
                    messages=messages,
                    temperature=0.3,
                )
                content = completion["choices"][0]["message"]["content"] or "{}"
            except Exception:
                return self._offline_narrative(context, sections, tone)

        data = self._parse_jsonish_object(content)
        if isinstance(data, dict):
            # Ensure only requested sections
            return {k: str(data.get(k, "")) for k in sections}

        # Fallback: single blob under 'executive_summary' if JSON parse fails
        return {sections[0] if sections else "executive_summary": content}

    def generate_subtasks(
        self,
        deterministic_subtasks: List[Dict[str, Any]],
        contract_excerpt: Optional[str],
        tone: str = "professional",
        model: str = "gpt-4o-mini",
    ) -> (List[Dict[str, Any]], Optional[str]):
        """
        Use GPT to polish/enrich module subtasks while keeping hours/calculations intact.
        """
        if not self.is_configured():
            raise RuntimeError("OPENAI_API_KEY not configured")

        client, client_mode = self._get_client()

        sys_prompt = (
            "You are a proposal writer. Rewrite the provided module subtasks into a concise, SOP-style "
            "format. Incorporate customer context when provided. DO NOT change hours, calculations, or "
            "the number of subtasks/tasks. Keep titles clear and outcomes-focused. "
            "Return ONLY a JSON array; no code fences or extra text. Use double quotes in JSON."
        )

        user_prompt = json.dumps({
            "tone": tone,
            "contract_excerpt": (contract_excerpt or "")[:2000],
            "instructions": [
                "Keep the same subtasks and tasks count.",
                "Preserve hours and calculations exactly.",
                "Include work_scope, estimate_basis, period_of_performance, reasonableness.",
                "If customer context is provided, weave it into work_scope and customer_context.",
                "Return JSON array of subtasks with keys: sequence, module_name, focus_area, work_scope, estimate_basis, period_of_performance, reasonableness, customer_context (optional), tasks (array of {title, calculation, hours, description optional}), total_hours.",
            ],
            "subtasks": deterministic_subtasks,
        })

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]

        content = None
        try:
            if client_mode == "v1":
                completion = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.4,
                )
                content = completion.choices[0].message.content or "[]"
            else:
                completion = client.ChatCompletion.create(
                    model=model,
                    messages=messages,
                    temperature=0.4,
                )
                content = completion["choices"][0]["message"]["content"] or "[]"
        except Exception:
            raise
        data = self._parse_jsonish_list(content)
        if data is not None:
            return data, content

        # Fallback: raise with raw content for diagnostics
        raise SubtaskAIError("AI subtask generation returned unparseable response", raw_content=content)

    def rewrite_narrative_section(
        self,
        estimation_data: Dict[str, Any],
        input_summary: Optional[Dict[str, Any]],
        section: str,
        prompt: Optional[str] = None,
        current_text: Optional[str] = None,
        tone: str = "professional",
        model: str = "gpt-4o-mini",
    ) -> Tuple[str, Optional[str]]:
        """
        Regenerate or refine a single narrative section with an inline prompt.
        Returns (text, raw_model_response).
        """
        if not self.is_configured():
            raise RuntimeError("OPENAI_API_KEY not configured")

        estimation_data = estimation_data or {}
        client, client_mode = self._get_client()

        context = self._build_narrative_context(estimation_data, input_summary)
        if estimation_data.get("narrative_sections"):
            context["existing_narrative"] = estimation_data["narrative_sections"]

        sys_prompt = (
            "You are an expert proposal writer editing one section of a report. "
            "Respect the provided facts and numbers. Apply the user's change request while keeping the tone aligned. "
            "Return ONLY JSON with a single key that matches the requested section."
        )
        user_payload = {
            "section": section,
            "tone": tone,
            "instructions": prompt or "",
            "current_text": current_text or "",
            "context": context,
        }
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": json.dumps(user_payload)},
        ]

        content: Optional[str] = None
        try:
            if client_mode == "v1":
                completion = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.35,
                )
                content = completion.choices[0].message.content or "{}"
            else:
                completion = client.ChatCompletion.create(
                    model=model,
                    messages=messages,
                    temperature=0.35,
                )
                content = completion["choices"][0]["message"]["content"] or "{}"
        except Exception:
            fallback = self._offline_narrative(context, [section], tone)
            return fallback.get(section, current_text or ""), None

        parsed = self._parse_jsonish_object(content or "{}")
        text = None
        if isinstance(parsed, dict):
            for key in (section, "text", "content", "value"):
                if parsed.get(key) is not None:
                    text = parsed.get(key)
                    break

        if text is None and content is not None:
            text = content.strip()

        final_text = str(text or current_text or "")
        return final_text, content

    def _build_narrative_context(
        self,
        estimation_data: Dict[str, Any],
        input_summary: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Normalize estimation data into a compact context for AI prompts."""
        estimation_data = estimation_data or {}
        result = estimation_data.get("estimation_result", {}) or {}
        modules_src = result.get("breakdown_by_module", {}) or {}
        roles_src = result.get("breakdown_by_role", {}) or {}
        module_items = modules_src.values() if isinstance(modules_src, dict) else modules_src
        role_items = roles_src.values() if isinstance(roles_src, dict) else roles_src
        context: Dict[str, Any] = {
            "summary": {
                "total_labor_hours": round(float(result.get("total_labor_hours", 0)), 2),
                "total_labor_cost": round(float(result.get("total_labor_cost", 0)), 2),
                "risk_reserve": round(float(result.get("risk_reserve", 0)), 2),
                "overhead_cost": round(float(result.get("overhead_cost", 0)), 2),
                "total_cost": round(float(result.get("total_cost", 0)), 2),
                "effective_hourly_rate": round(float(result.get("effective_hourly_rate", 0)), 2),
                "complexity": (input_summary or {}).get("complexity"),
                "module_count": (input_summary or {}).get("module_count"),
            },
            "modules": [
                {
                    "name": m.get("module_name"),
                    "focus_area": m.get("focus_area"),
                    "hours": round(float(m.get("hours", 0)), 1),
                    "cost": round(float(m.get("cost", 0)), 2),
                }
                for m in module_items
            ],
            "roles": [
                {
                    "role": r.get("role_name"),
                    "hours": round(float(r.get("hours", 0)), 1),
                    "rate": round(float(r.get("effective_rate", 0)), 2),
                    "cost": round(float(r.get("cost", 0)), 2),
                }
                for r in role_items
            ],
        }
        if estimation_data.get("project_info"):
            context["project_info"] = estimation_data["project_info"]
        if estimation_data.get("module_subtasks"):
            context["module_subtasks"] = estimation_data["module_subtasks"]
        if estimation_data.get("contract_source"):
            context["contract_source"] = estimation_data["contract_source"]
        if estimation_data.get("narrative_sections"):
            context["narrative_sections"] = estimation_data["narrative_sections"]
        if estimation_data.get("odc_items") is not None:
            context["odc_items"] = estimation_data["odc_items"]
        if estimation_data.get("fixed_price_items") is not None:
            context["fixed_price_items"] = estimation_data["fixed_price_items"]
        if estimation_data.get("hardware_subtotal") is not None:
            context["hardware_subtotal"] = estimation_data["hardware_subtotal"]
        if estimation_data.get("warranty_months") is not None:
            context["warranty_months"] = estimation_data["warranty_months"]
        if estimation_data.get("warranty_cost") is not None:
            context["warranty_cost"] = estimation_data["warranty_cost"]
        if input_summary:
            context["input_summary"] = input_summary
        return context

    def _get_client(self):
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
        return client, client_mode

    def _parse_jsonish_list(self, content: str) -> Optional[List[Dict[str, Any]]]:
        """
        Attempt to parse model output into a list of subtasks even if wrapped
        in markdown code fences or non-strict JSON.
        """
        text = content.strip()
        # Strip code fences if present
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1].strip()

        # Try strict JSON (double-quoted)
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data  # type: ignore[return-value]
            if isinstance(data, dict):
                for key in ("subtasks", "module_subtasks", "tasks", "data"):
                    if isinstance(data.get(key), list):
                        return data[key]  # type: ignore[return-value]
        except Exception:
            pass

        # Try lenient single-quote JSON
        try:
            fixed = text.replace("'", "\"")
            data = json.loads(fixed)
            if isinstance(data, list):
                return data  # type: ignore[return-value]
            if isinstance(data, dict):
                for key in ("subtasks", "module_subtasks", "tasks", "data"):
                    if isinstance(data.get(key), list):
                        return data[key]  # type: ignore[return-value]
        except Exception:
            pass

        # Try to locate first JSON array in the text
        try:
            start = text.index("[")
            end = text.rindex("]")
            snippet = text[start:end+1]
            data = json.loads(snippet)
            if isinstance(data, list):
                return data  # type: ignore[return-value]
        except Exception:
            pass

        # As a last resort, use ast.literal_eval for loose Python-like lists
        try:
            import ast
            data = ast.literal_eval(text)
            if isinstance(data, list):
                return data  # type: ignore[return-value]
            if isinstance(data, dict):
                for key in ("subtasks", "module_subtasks", "tasks", "data"):
                    if isinstance(data.get(key), list):
                        return data[key]  # type: ignore[return-value]
        except Exception:
            pass

        return None

    def _parse_jsonish_object(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to parse model output into a dict even if wrapped in code fences or
        using single quotes.
        """
        text = content.strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1].strip()

        # Strict JSON
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

        # Lenient single-quote JSON
        try:
            fixed = text.replace("'", "\"")
            data = json.loads(fixed)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

        # Extract first JSON object braces
        try:
            start = text.index("{")
            end = text.rindex("}")
            snippet = text[start:end+1]
            data = json.loads(snippet)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

        # Final attempt: ast.literal_eval
        try:
            import ast
            data = ast.literal_eval(text)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

        return None


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
