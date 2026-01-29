import os
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

PROMPTS_DIR = Path(os.getenv("PROMPTS_DIR", Path(__file__).resolve().parents[1] / "prompts"))
SUBTASK_PROMPTS_DIR = PROMPTS_DIR / "subtasks"


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
            "Return ONLY valid JSON (no code fences, no extra text) with keys matching the requested sections. "
            "Each value MUST be a single string paragraph with 2-5 sentences (no lists or objects). "
            "Do NOT include JSON, braces, or key-value formatting inside the section text. "
            "Use context (scope_outline, contract_highlights, project_info, security_protocols, compliance_frameworks, additional_assumptions, style_guide) "
            "to add human context beyond raw numbers. "
            "If contract_source/excerpt is provided, weave in 1-2 relevant details without quoting large blocks."
        )

        user_payload = {
            "tone": tone,
            "sections": sections,
            "context": context,
            "section_guidance": self._build_section_guidance(sections),
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
            # Ensure only requested sections and always return string paragraphs
            return {k: self._normalize_section_text(k, data.get(k, "")) for k in sections}

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
            "Make each subtask distinct and tailored to its module_name and focus_area; avoid repeating "
            "phrases across modules. Use module_guidance when provided. "
            "Return ONLY a JSON array; no code fences or extra text. Use double quotes in JSON."
        )

        module_guidance = self._build_subtask_guidance(deterministic_subtasks, contract_excerpt)

        user_prompt = json.dumps({
            "tone": tone,
            "contract_excerpt": (contract_excerpt or "")[:2000],
            "module_guidance": module_guidance,
            "instructions": [
                "Keep the same subtasks and tasks count.",
                "Preserve hours and calculations exactly.",
                "Include work_scope, estimate_basis, period_of_performance, reasonableness.",
                "Use module_guidance keyed by module_id (or module_name) when present.",
                "If customer context is provided, weave it into work_scope and customer_context.",
                "Preserve security_protocols and compliance_frameworks if provided.",
                "Do not include helper fields like module_guidance in the output.",
                "Return JSON array of subtasks with keys: sequence, module_name, focus_area, work_scope, estimate_basis, period_of_performance, reasonableness, security_protocols (optional), compliance_frameworks (optional), customer_context (optional), tasks (array of {title, calculation, hours, description optional}), total_hours.",
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
            "Return ONLY JSON with a single key that matches the requested section. "
            "The value must be a single string paragraph with 2-4 sentences (no lists or objects). "
            "Do NOT include JSON, braces, or key-value formatting inside the section text. "
            "Use scope_outline, contract_highlights, and style_guide from context when relevant."
        )
        user_payload = {
            "section": section,
            "tone": tone,
            "instructions": prompt or "",
            "current_text": current_text or "",
            "context": context,
            "section_guidance": self._build_section_guidance([section]),
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

        final_text = self._normalize_section_text(section, text or current_text or "")
        return final_text, content

    def generate_additional_assumptions(
        self,
        prompt_template: str,
        context: Dict[str, Any],
        model: str = "gpt-4o-mini",
    ) -> Tuple[str, Optional[str]]:
        """
        Generate the additional assumptions section from a prompt template and context.
        Returns (text, raw_model_response).
        """
        return self._generate_from_prompt_template(prompt_template, context, model=model, temperature=0.25)

    def generate_additional_comments(
        self,
        prompt_template: str,
        context: Dict[str, Any],
        model: str = "gpt-4o-mini",
    ) -> Tuple[str, Optional[str]]:
        """Generate additional comments text from a prompt template and context."""
        return self._generate_from_prompt_template(prompt_template, context, model=model, temperature=0.25)

    def generate_security_protocols(
        self,
        prompt_template: str,
        context: Dict[str, Any],
        model: str = "gpt-4o-mini",
    ) -> Tuple[str, Optional[str]]:
        """Generate security protocols text from a prompt template and context."""
        return self._generate_from_prompt_template(prompt_template, context, model=model, temperature=0.2)

    def generate_compliance_frameworks(
        self,
        prompt_template: str,
        context: Dict[str, Any],
        model: str = "gpt-4o-mini",
    ) -> Tuple[str, Optional[str]]:
        """Generate compliance frameworks text from a prompt template and context."""
        return self._generate_from_prompt_template(prompt_template, context, model=model, temperature=0.2)

    def _generate_from_prompt_template(
        self,
        prompt_template: str,
        context: Dict[str, Any],
        model: str = "gpt-4o-mini",
        temperature: float = 0.25,
    ) -> Tuple[str, Optional[str]]:
        if not self.is_configured():
            raise RuntimeError("OPENAI_API_KEY not configured")

        client, client_mode = self._get_client()
        rendered = self._render_prompt_template(prompt_template, context)
        system_prompt, user_prompt = self._split_prompt_template(rendered)

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        content: Optional[str] = None
        if client_mode == "v1":
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            content = completion.choices[0].message.content or ""
        else:
            completion = client.ChatCompletion.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            content = completion["choices"][0]["message"]["content"] or ""

        return (content or "").strip(), content

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
        project_info = estimation_data.get("project_info")
        if project_info:
            context["project_info"] = project_info
            if project_info.get("security_protocols"):
                context["security_protocols"] = project_info.get("security_protocols")
            if project_info.get("compliance_frameworks"):
                context["compliance_frameworks"] = project_info.get("compliance_frameworks")
            if project_info.get("additional_assumptions"):
                context["additional_assumptions"] = project_info.get("additional_assumptions")
        if estimation_data.get("module_subtasks"):
            module_subtasks = estimation_data["module_subtasks"]
            context["module_subtasks"] = self._trim_module_subtasks(module_subtasks)
            context["scope_outline"] = self._build_scope_outline(module_subtasks)
        if estimation_data.get("contract_source"):
            contract_src = estimation_data["contract_source"]
            context["contract_source"] = contract_src
            excerpt = contract_src.get("excerpt") if isinstance(contract_src, dict) else None
            if excerpt:
                context["contract_highlights"] = self._extract_contract_highlights(str(excerpt))
        style_guide = estimation_data.get("style_guide")
        if style_guide:
            context["style_guide"] = self._trim_text(style_guide, 2000)
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

    def _build_section_guidance(self, sections: List[str]) -> Dict[str, str]:
        guidance = {
            "executive_summary": (
                "Summarize the project intent and scope in 3-5 sentences. "
                "Include key project_info fields when present (project name, FY, POC, location), "
                "1-2 key figures (hours or cost), and a brief services summary based on the selected modules. "
                "If provided, mention security_protocols and compliance_frameworks. "
                "Weave in contract_highlights or scope_outline when relevant."
            ),
            "assumptions": (
                "State delivery assumptions tied to the scope and contract context. "
                "Incorporate any additional_assumptions or project_info notes when provided. "
                "Address access to stakeholders or data, dependencies, approvals, schedule, and "
                "security/compliance where applicable. Avoid restating raw numbers."
            ),
            "risks": (
                "Describe 2-3 key risks linked to the scope or contract context and "
                "their potential impact. Avoid generic risks that could apply to any project."
            ),
            "recommendations": (
                "Provide action-oriented next steps aligned to scope and governance. "
                "Examples include validating assumptions, confirming interfaces, or "
                "sequencing work to reduce delivery risk."
            ),
            "next_steps": (
                "Provide concise, action-oriented next steps aligned to scope and governance."
            ),
        }
        return {s: guidance[s] for s in sections if s in guidance}

    def build_subtask_guidance(
        self,
        subtasks: List[Dict[str, Any]],
        contract_excerpt: Optional[str],
    ) -> Dict[str, str]:
        return self._build_subtask_guidance(subtasks, contract_excerpt)

    def build_subtask_guidance_debug(
        self,
        subtasks: List[Dict[str, Any]],
        contract_excerpt: Optional[str],
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        return self._build_subtask_guidance_with_sources(subtasks, contract_excerpt)

    def _build_subtask_guidance(
        self,
        subtasks: List[Dict[str, Any]],
        contract_excerpt: Optional[str],
    ) -> Dict[str, str]:
        guidance, _sources = self._build_subtask_guidance_with_sources(subtasks, contract_excerpt)
        return guidance

    def _build_subtask_guidance_with_sources(
        self,
        subtasks: List[Dict[str, Any]],
        contract_excerpt: Optional[str],
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        if not subtasks:
            return {}, {}
        guidance: Dict[str, str] = {}
        sources: Dict[str, str] = {}
        excerpt = self._trim_text(contract_excerpt, 1800)
        highlights = self._extract_contract_highlights(excerpt) if excerpt else []
        highlight_text = "; ".join(highlights)

        for subtask in subtasks:
            module_id = str(subtask.get("module_id") or "").strip()
            module_name = str(subtask.get("module_name") or "").strip()
            focus_area = str(subtask.get("focus_area") or "").strip()
            template, template_name = self._load_subtask_prompt_template(module_id, focus_area)
            if not template:
                continue
            tasks = subtask.get("tasks") or []
            task_titles = [t.get("title") for t in tasks if t.get("title")]
            context = {
                "MODULE_NAME": module_name,
                "MODULE_ID": module_id,
                "FOCUS_AREA": focus_area,
                "FOCUS_LABEL": subtask.get("focus_label") or "",
                "TASK_TITLES": ", ".join(task_titles),
                "CONTRACT_HIGHLIGHTS": highlight_text,
            }
            key = module_id or module_name or f"module_{len(guidance) + 1}"
            guidance[key] = self._render_prompt_template(template, context)
            if template_name:
                sources[key] = template_name
        return guidance, sources

    def _load_subtask_prompt_template(self, module_id: str, focus_area: str) -> Tuple[Optional[str], Optional[str]]:
        candidates: List[str] = []
        if module_id:
            candidates.extend([
                f"{module_id}.txt",
                f"subtask_{module_id}.txt",
            ])
        if focus_area:
            candidates.extend([
                f"{focus_area}.txt",
                f"subtask_{focus_area}.txt",
            ])
        for name in candidates:
            path = SUBTASK_PROMPTS_DIR / name
            if not path.exists():
                continue
            try:
                return path.read_text(encoding="utf-8"), name
            except Exception:
                continue
        return None, None

    def _render_prompt_template(self, template: str, context: Dict[str, Any]) -> str:
        rendered = template or ""
        for key, value in (context or {}).items():
            placeholder = f"[{key}]"
            rendered = rendered.replace(placeholder, str(value or ""))
        return rendered

    def _split_prompt_template(self, template: str) -> Tuple[Optional[str], str]:
        if not template:
            return None, ""
        normalized = template.strip()
        parts = re.split(r"\nUSER\n", normalized, flags=re.IGNORECASE)
        if len(parts) == 2:
            system_block = re.sub(r"^SYSTEM\n?", "", parts[0].strip(), flags=re.IGNORECASE)
            user_block = parts[1].strip()
            return system_block or None, user_block
        return None, normalized

    def _trim_text(self, text: Any, max_chars: int) -> str:
        if text is None:
            return ""
        cleaned = self._compact_whitespace(str(text))
        if max_chars and max_chars > 0 and len(cleaned) > max_chars:
            return cleaned[:max_chars]
        return cleaned

    def _compact_whitespace(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    def _split_into_sentences(self, text: str) -> List[str]:
        cleaned = self._compact_whitespace(text)
        if not cleaned:
            return []
        parts = re.split(r"(?<=[.!?])\s+", cleaned)
        return [p.strip() for p in parts if p.strip()]

    def _extract_contract_highlights(
        self,
        excerpt: str,
        max_sentences: int = 4,
        max_chars: int = 900,
    ) -> List[str]:
        cleaned = self._compact_whitespace(excerpt)
        sentences = self._split_into_sentences(cleaned)
        if not sentences:
            return []
        keywords = [
            "scope",
            "deliverable",
            "deliverables",
            "objective",
            "requirements",
            "shall",
            "must",
            "period of performance",
            "timeline",
            "schedule",
            "security",
            "compliance",
            "rmf",
            "dfars",
            "cloud",
            "migration",
            "data",
            "integration",
            "stakeholder",
            "reporting",
        ]
        prioritized = [s for s in sentences if any(k in s.lower() for k in keywords)]
        if not prioritized:
            prioritized = sentences[:2]
        highlights: List[str] = []
        total = 0
        for sentence in prioritized:
            if sentence in highlights:
                continue
            if total + len(sentence) > max_chars and highlights:
                break
            highlights.append(sentence)
            total += len(sentence)
            if len(highlights) >= max_sentences:
                break
        return highlights

    def _trim_module_subtasks(self, module_subtasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        trimmed: List[Dict[str, Any]] = []
        for subtask in module_subtasks or []:
            tasks = subtask.get("tasks") or []
            task_titles = [t.get("title") for t in tasks if t.get("title")]
            trimmed.append({
                "module_name": subtask.get("module_name"),
                "focus_area": subtask.get("focus_area") or subtask.get("focus_label"),
                "work_scope": self._trim_text(subtask.get("work_scope"), 320),
                "estimate_basis": self._trim_text(subtask.get("estimate_basis"), 260),
                "period_of_performance": self._trim_text(subtask.get("period_of_performance"), 220),
                "reasonableness": self._trim_text(subtask.get("reasonableness"), 220),
                "total_hours": subtask.get("total_hours"),
                "security_protocols": self._trim_text(subtask.get("security_protocols"), 220),
                "compliance_frameworks": self._trim_text(subtask.get("compliance_frameworks"), 220),
                "key_tasks": task_titles[:5],
                "customer_context": self._trim_text(subtask.get("customer_context"), 400),
            })
        return trimmed

    def _build_scope_outline(self, module_subtasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        outline: List[Dict[str, Any]] = []
        for subtask in module_subtasks or []:
            tasks = subtask.get("tasks") or []
            task_titles = [t.get("title") for t in tasks if t.get("title")]
            outline.append({
                "module_name": subtask.get("module_name"),
                "focus_area": subtask.get("focus_area") or subtask.get("focus_label"),
                "work_scope": self._trim_text(subtask.get("work_scope"), 220),
                "key_tasks": task_titles[:3],
            })
        return outline

    def _coerce_narrative_text(self, value: Any) -> str:
        """Ensure narrative sections are returned as plain text paragraphs."""
        if value is None:
            return ""
        if isinstance(value, str):
            text = value.strip()
            parsed = self._coerce_jsonish_string(text)
            if parsed is not None:
                return parsed
            return text
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, list):
            return self._format_list_value(value)
        if isinstance(value, dict):
            return self._format_dict_value(value)
        try:
            return json.dumps(value, ensure_ascii=True)
        except Exception:
            return str(value)

    def _normalize_section_text(self, section: str, value: Any) -> str:
        structured = self._extract_structured_value(value)
        if structured is not None:
            return self._format_structured_section(section, structured)
        return self._coerce_narrative_text(value)

    def _extract_structured_value(self, value: Any) -> Optional[Any]:
        if isinstance(value, (dict, list)):
            return value
        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        if text.startswith("{") and text.endswith("}"):
            parsed = self._parse_jsonish_object(text)
            if isinstance(parsed, dict):
                return parsed
        if text.startswith("[") and text.endswith("]"):
            parsed = self._parse_jsonish_list(text)
            if parsed is not None:
                return parsed
        if "{" in text and "}" in text:
            try:
                start = text.index("{")
                end = text.rindex("}")
                snippet = text[start:end + 1]
                parsed = self._parse_jsonish_object(snippet)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        if "[" in text and "]" in text:
            try:
                start = text.index("[")
                end = text.rindex("]")
                snippet = text[start:end + 1]
                parsed = self._parse_jsonish_list(snippet)
                if parsed is not None:
                    return parsed
            except Exception:
                pass
        return None

    def _coerce_jsonish_string(self, text: str) -> Optional[str]:
        structured = self._extract_structured_value(text)
        if structured is None:
            return None
        if isinstance(structured, dict):
            return self._format_dict_value(structured)
        if isinstance(structured, list):
            return self._format_list_value(structured)
        return None

    def _format_structured_section(self, section: str, value: Any) -> str:
        if section == "executive_summary" and isinstance(value, dict):
            return self._format_executive_summary(value)
        prefix = {
            "assumptions": "Assume",
            "risks": "Key risk",
            "recommendations": "Recommendation",
            "next_steps": "Next step",
        }.get(section)
        items: List[str] = []
        if isinstance(value, dict):
            for key, val in value.items():
                val_text = self._coerce_narrative_text(val)
                if not val_text:
                    continue
                if not self._looks_like_sentence(val_text):
                    label = self._format_key_label(key)
                    if label and label.lower() not in val_text.lower():
                        val_text = f"{label} {val_text}".strip()
                    if prefix:
                        val_text = f"{prefix} {val_text}".strip()
                items.append(self._ensure_sentence(val_text))
        elif isinstance(value, list):
            for item in value:
                val_text = self._coerce_narrative_text(item)
                if not val_text:
                    continue
                if not self._looks_like_sentence(val_text) and prefix:
                    val_text = f"{prefix} {val_text}".strip()
                items.append(self._ensure_sentence(val_text))
        paragraph = " ".join([p for p in items if p])
        return paragraph.strip()

    def _format_executive_summary(self, data: Dict[str, Any]) -> str:
        project_name = data.get("project_name") or ""
        total_hours = self._safe_float(data.get("total_labor_hours"))
        total_cost = self._safe_float(data.get("total_cost"))
        labor_cost = self._safe_float(data.get("total_labor_cost"))
        risk_reserve = self._safe_float(data.get("risk_reserve"))
        overhead_cost = self._safe_float(data.get("overhead_cost"))
        rate = self._safe_float(data.get("effective_hourly_rate"))
        complexity = self._format_complexity(data.get("complexity"))
        module_count = self._safe_int(data.get("module_count"))
        modules = data.get("modules") if isinstance(data.get("modules"), list) else []
        module_names = [m.get("name") for m in modules if isinstance(m, dict) and m.get("name")]

        sentences: List[str] = []
        if project_name:
            sentences.append(f"This estimate supports {project_name}.")
        if total_hours is not None or total_cost is not None:
            parts = []
            if total_hours is not None:
                parts.append(f"approximately {total_hours:,.1f} labor hours")
            if total_cost is not None:
                parts.append(f"a total cost of ${total_cost:,.2f}")
            if parts:
                sentences.append(f"The projected effort includes {', and '.join(parts)}.")
        cost_parts = []
        if labor_cost is not None:
            cost_parts.append(f"labor ${labor_cost:,.2f}")
        if risk_reserve is not None:
            cost_parts.append(f"risk reserve ${risk_reserve:,.2f}")
        if overhead_cost is not None:
            cost_parts.append(f"overhead ${overhead_cost:,.2f}")
        if cost_parts:
            sentences.append(f"Cost composition reflects {', '.join(cost_parts)}.")
        if rate is not None or complexity or module_count:
            detail_parts = []
            if rate is not None:
                detail_parts.append(f"a blended rate of about ${rate:,.2f} per hour")
            if complexity:
                detail_parts.append(f"{complexity} complexity")
            if module_count is not None:
                detail_parts.append(f"{module_count} modules")
            if detail_parts:
                sentences.append(f"The profile reflects {', '.join(detail_parts)}.")
        if module_names:
            sentences.append(f"Modules include {', '.join(module_names)}.")

        if not sentences:
            return self._format_dict_value(data)
        return " ".join(sentences).strip()

    def _safe_float(self, value: Any) -> Optional[float]:
        try:
            return float(value)
        except Exception:
            return None

    def _safe_int(self, value: Any) -> Optional[int]:
        try:
            return int(float(value))
        except Exception:
            return None

    def _format_complexity(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        val = str(value).strip()
        mapping = {
            "S": "low",
            "M": "medium",
            "L": "high",
            "XL": "very high",
            "LOW": "low",
            "MEDIUM": "medium",
            "HIGH": "high",
            "VERY HIGH": "very high",
        }
        return mapping.get(val.upper(), val)

    def _ensure_sentence(self, text: str) -> str:
        cleaned = (text or "").strip()
        if not cleaned:
            return ""
        if cleaned[-1] not in ".!?":
            cleaned += "."
        return cleaned

    def _looks_like_sentence(self, text: str) -> bool:
        if not text:
            return False
        cleaned = text.strip()
        if not cleaned:
            return False
        return cleaned[-1] in ".!?" or " " in cleaned

    def _format_key_label(self, key: str) -> str:
        label = str(key or "").replace("_", " ").replace("-", " ").strip()
        if not label:
            return "Detail"
        return label[0].upper() + label[1:]

    def _format_dict_value(self, data: Dict[str, Any], inline: bool = False) -> str:
        parts: List[str] = []
        for key, val in data.items():
            val_text = self._coerce_narrative_text(val)
            if not val_text:
                continue
            label = self._format_key_label(key)
            parts.append(f"{label}: {val_text}")
        text = "; ".join(parts)
        if not inline and text and text[-1] not in ".!?":
            text += "."
        return text

    def _format_list_value(self, items: List[Any]) -> str:
        parts: List[str] = []
        for item in items:
            if item is None:
                continue
            if isinstance(item, dict):
                chunk = self._format_dict_value(item, inline=True)
            else:
                chunk = self._coerce_narrative_text(item)
            if chunk:
                parts.append(chunk)
        text = "; ".join(parts)
        if text and text[-1] not in ".!?":
            text += "."
        return text

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
        project_info = context.get("project_info", {}) or {}

        total_hours = summary.get("total_labor_hours") or 0
        total_cost = summary.get("total_cost") or 0
        risk_reserve = summary.get("risk_reserve") or 0
        overhead_cost = summary.get("overhead_cost") or 0
        eff_rate = summary.get("effective_hourly_rate") or 0
        complexity = summary.get("complexity") or "M"
        mod_count = summary.get("module_count") or len(modules)

        module_names = ", ".join([m.get("name") or "module" for m in modules]) or "selected modules"
        top_roles = ", ".join([r.get("role") or "role" for r in roles[:3]])
        project_bits = []
        if project_info.get("project_name"):
            project_bits.append(str(project_info.get("project_name")))
        if project_info.get("fy"):
            project_bits.append(f"FY {project_info.get('fy')}")
        if project_info.get("site_location"):
            project_bits.append(str(project_info.get("site_location")))
        if project_info.get("government_poc"):
            project_bits.append(f"POC: {project_info.get('government_poc')}")
        project_intro = ", ".join(project_bits)
        security_protocols = project_info.get("security_protocols")
        compliance_frameworks = project_info.get("compliance_frameworks")
        additional_assumptions = project_info.get("additional_assumptions")

        text: Dict[str, str] = {}

        if "executive_summary" in secs:
            sentences = []
            if project_intro:
                sentences.append(f"Project overview: {project_intro}.")
            sentences.append(
                f"This estimate covers {mod_count} {('module' if mod_count==1 else 'modules')} "
                f"with a {complexity} complexity profile and approximately {total_hours:.0f} labor hours, "
                f"totaling ${total_cost:,.2f} (risk reserve ${risk_reserve:,.2f}, overhead ${overhead_cost:,.2f})."
            )
            sentences.append(f"Services include {module_names} aligned to the RFP scope.")
            if security_protocols or compliance_frameworks:
                sec_bits = []
                if security_protocols:
                    sec_bits.append(f"security protocols: {security_protocols}")
                if compliance_frameworks:
                    sec_bits.append(f"compliance frameworks: {compliance_frameworks}")
                sentences.append("Security posture highlights " + "; ".join(sec_bits) + ".")
            sentences.append(f"The effective blended rate is about ${eff_rate:,.2f} per hour.")
            text["executive_summary"] = " ".join(sentences[:5])

        if "assumptions" in secs:
            assumption_sentences = [
                f"Estimates assume a typical staffing mix ({top_roles or 'multi-disciplinary team'}) and standard project cadence.",
                "Module sequencing accounts for prerequisites, dependency alignment, and access to required data and stakeholders.",
                "Security reviews, compliance checkpoints, and approvals are aligned with the proposed schedule.",
            ]
            if additional_assumptions:
                trimmed = self._trim_text(additional_assumptions, 240)
                assumption_sentences.append(f"Additional assumptions provided: {trimmed}.")
            text["assumptions"] = " ".join(assumption_sentences[:4])

        if "risks" in secs:
            text["risks"] = (
                f"Primary risks include scope growth and integration unknowns that could extend effort beyond the baseline {total_hours:.0f} hours. "
                f"Multi-module dependencies ({module_names}) may impact sequencing and throughput. "
                f"The allocated risk reserve of ${risk_reserve:,.2f} is intended to buffer typical variance."
            )

        if "recommendations" in secs:
            text["recommendations"] = (
                "Begin with a short planning sprint to refine scope and confirm interfaces. "
                "Sequence delivery to realize early value while de-risking complex integrations. "
                "Review staffing against milestones and adjust to maintain schedule confidence."
            )

        return text
