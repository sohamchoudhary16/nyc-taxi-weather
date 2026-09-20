-- NOTE: This macro does not detect DST spring-forward gaps.
-- The Python normaliser (timestamps.py) does. For months spanning
-- DST transitions (March, November), add gap detection here or
-- normalise in Python before loading.
{# Wall-clock local time -> canonical UTC. The single SQL definition of the
   timezone contract; mirrors src/taxi/timestamps.py for the Python path. #}
{% macro local_to_utc(column, tz) %}
  {%- if target.type == 'duckdb' -%}
    (({{ column }})::TIMESTAMP AT TIME ZONE '{{ tz }}')
  {%- else -%}
    to_utc_timestamp({{ column }}, '{{ tz }}')
  {%- endif -%}
{% endmacro %}

{% macro utc_to_local(column, tz) %}
  {%- if target.type == 'duckdb' -%}
    (({{ column }}) AT TIME ZONE '{{ tz }}')
  {%- else -%}
    from_utc_timestamp({{ column }}, '{{ tz }}')
  {%- endif -%}
{% endmacro %}

{% macro trunc_hour(column) %}
  {%- if target.type == 'duckdb' -%}
    date_trunc('hour', {{ column }})
  {%- else -%}
    date_trunc('HOUR', {{ column }})
  {%- endif -%}
{% endmacro %}

{% macro date_diff_seconds(start, end) %}
  {%- if target.type == 'duckdb' -%}
    date_diff('second', {{ start }}, {{ end }})
  {%- else -%}
    datediff(second, {{ start }}, {{ end }})
  {%- endif -%}
{% endmacro %}

{% macro extract_dow(ts) %}
  {%- if target.type == 'duckdb' -%}
    extract(dow from {{ ts }})
  {%- else -%}
    (dayofweek({{ ts }}) - 1)
  {%- endif -%}
{% endmacro %}

{% macro bool_or_agg(expr) %}
  {%- if target.type == 'duckdb' -%}
    bool_or({{ expr }})
  {%- else -%}
    max({{ expr }})
  {%- endif -%}
{% endmacro %}

{% macro safe_filter(agg_expr, value_expr, condition) %}
  {%- if target.type == 'duckdb' -%}
    {{ agg_expr }}({{ value_expr }}) filter (where {{ condition }})
  {%- else -%}
    {{ agg_expr }}(case when {{ condition }} then {{ value_expr }} end)
  {%- endif -%}
{% endmacro %}

{% macro to_timestamptz(ts_string) %}
  {%- if target.type == 'duckdb' -%}
    timestamptz '{{ ts_string }} 00:00:00+00'
  {%- else -%}
    to_utc_timestamp(cast('{{ ts_string }}' as timestamp), 'UTC')
  {%- endif -%}
{% endmacro %}
