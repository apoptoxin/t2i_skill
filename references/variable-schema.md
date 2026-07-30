# Cover variable schema

```json
{
  "layout_type": "process | comparison | evidence",
  "top_label": "at most 8 characters",
  "title_line_1": "at most 14 visible characters",
  "title_line_2": "at most 14 visible characters",
  "highlight_phrase": "short supporting contrast",
  "evidence_a": "first visible proof or group",
  "evidence_b": "second visible proof or group",
  "evidence_c": "third visible proof or supporting change",
  "result_label": "short label such as 结果",
  "result_value": "the promised or observed result",
  "bottom_summary": "one short judgment",
  "background_objects": ["2 to 5 concrete visual objects"],
  "accent_color": "orange",
  "brand_mode": "text | none",
  "brand_name": "project account name or empty"
}
```

All numbers must occur in the source script. Text from a Demo must not appear
unless it also occurs in the source script. `brand_name` is controlled only by
the current project's `.cover-skill/config.json`.

