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
