{{/* chezmoi:modify-template */}}
{{- $begin := "<!-- macos-workstation:agent-harness:begin -->" -}}
{{- $end := "<!-- macos-workstation:agent-harness:end -->" -}}
{{- $block := `<!-- macos-workstation:agent-harness:begin -->
## Agent-harness execution environment

- For installed agent-harness gh/review entrypoints, use the workstation launcher:

      "$HOME/.local/bin/agent-harness-exec" "<absolute installed harness entrypoint>" <args...>

- Read the relevant SKILL.md first and resolve the entrypoint from that actual installed skill. Do not guess a clone path or use a development checkout.
- The launcher selects GNU commands only for the harness and its descendants on macOS. Execute it as a separate process; never source it or add its GNU directory to the global PATH.
- Keep pi itself, review-target tests, and ordinary commands outside the launcher, in their normal environment. Run them as separate commands, not children of a launched harness.
- If the launcher rejects an entrypoint or reports missing dependencies, report the blocker. Do not bypass it, patch the installed skill package, or install dependencies automatically.
- Continue to follow the loaded skills for API permissions, review content, and posting rules. The launcher is not an authorization or security boundary.
<!-- macos-workstation:agent-harness:end -->` -}}
{{- $before := splitList $begin .chezmoi.stdin -}}
{{- $ends := splitList $end .chezmoi.stdin -}}
{{- if and (eq (len $before) 1) (eq (len $ends) 1) -}}
  {{- .chezmoi.stdin -}}
  {{- if ne .chezmoi.stdin "" -}}
    {{- if not (hasSuffix "\n" .chezmoi.stdin) -}}{{ "\n" }}{{- end -}}
    {{- "\n" -}}
  {{- end -}}
  {{- printf "%s\n" $block -}}
{{- else if and (eq (len $before) 2) (eq (len $ends) 2) -}}
  {{- $after := splitList $end (index $before 1) -}}
  {{- if ne (len $after) 2 -}}{{ fail "agent-harness instruction markers are out of order" }}{{- end -}}
  {{- printf "%s%s%s" (index $before 0) $block (index $after 1) -}}
{{- else -}}
  {{- fail "agent-harness instruction markers are incomplete or duplicated; preserve the file and repair them manually" -}}
{{- end -}}
