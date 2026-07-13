select customer_id, name, created_at from {{ ref('stg_customers') }}
