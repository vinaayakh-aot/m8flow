"""Simple node-wire connector scenarios, seeded as stand-alone process models.

* customer-ledger   postgres_v2/DoSQL against the stack's own database (offline, no credentials)
* db-heartbeat      timer start event + postgres_v2/DoSQL (left in draft so it adds no background load)
* partner-api-check http/GetRequestV2 + http/PostRequestV2 against httpbin.org (needs internet egress;
                    the proxy's SSRF guard blocks every in-stack host)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bpmn_builder import Diagram, py
from templates import PG_PROFILE, form, integer, number, text

# Process ids equal the model id: the host derives a new model's primary_process_id
# from its id and does not update it when the BPMN is replaced.


@dataclass
class ConnectorModel:
    model_id: str
    name: str
    description: str
    diagram: Diagram
    forms: dict[str, dict] = field(default_factory=dict)
    publish: bool = True
    needs_internet: bool = False

    @property
    def bpmn_file(self) -> str:
        return f"{self.model_id}.bpmn"


def _pg(sql: str, values: str | None = None, fetch: bool = False) -> dict[str, str | None]:
    schema = "{'sql': " + repr(sql)
    if values:
        schema += ", 'values': " + values
    if fetch:
        schema += ", 'fetch_results': True"
    return {"m8flow_profile": PG_PROFILE, "database_connection_str": None, "schema": schema + "}"}


def customer_ledger() -> ConnectorModel:
    d = Diagram("customer-ledger", "Customer Ledger Entry",
                documentation="Records a customer payment in PostgreSQL through the node-wire postgres_v2 connector.")
    d.lane("Submitters", 0, 0)
    d.start("start_entry", "Payment received", 0, 0)
    d.user("enter_payment", "Enter payment", 1, 0, form="ledger-entry")
    d.service("ensure_table", "Ensure ledger table", 2, 0, "postgres_v2/DoSQL", _pg(
        "CREATE TABLE IF NOT EXISTS perf_customer_ledger (id serial PRIMARY KEY, customer text, "
        "amount numeric, invoice text, created_at timestamptz DEFAULT now())"), "table_result")
    d.service("insert_entry", "Insert ledger entry", 3, 0, "postgres_v2/DoSQL", _pg(
        "INSERT INTO perf_customer_ledger (customer, amount, invoice) VALUES (%s, %s, %s) RETURNING id",
        "[customer, amount, invoice]", fetch=True), "insert_result",
        post="entry_id = insert_result['command_response']['body']['body'][0][0]")
    d.service("read_balance", "Read customer balance", 4, 0, "postgres_v2/DoSQL", _pg(
        "SELECT count(*), coalesce(sum(amount), 0)::float FROM perf_customer_ledger WHERE customer = %s",
        "[customer]", fetch=True), "balance_result",
        post="entries, balance = balance_result['command_response']['body']['body'][0]")
    d.end("end_entry", "Entry recorded", 5, 0)
    for a, b in [("start_entry", "enter_payment"), ("enter_payment", "ensure_table"),
                 ("ensure_table", "insert_entry"), ("insert_entry", "read_balance"), ("read_balance", "end_entry")]:
        d.flow(a, b)
    forms = {"ledger-entry": form("Ledger entry", {
        "customer": text("Customer"), "amount": number("Amount (USD)", minimum=0), "invoice": text("Invoice number"),
    }, ["customer", "amount", "invoice"])}
    return ConnectorModel("customer-ledger", "Customer Ledger Entry",
                          "PostgreSQL connector scenario: create, insert and aggregate.", d, forms)


def db_heartbeat() -> ConnectorModel:
    d = Diagram("db-heartbeat", "Database Heartbeat",
                documentation="Scheduled health probe: every 15 minutes, run SELECT 1 through the postgres connector.")
    d.start("start_heartbeat", "Every 15 minutes", 0, 0, timer=("cycle", py("R/PT15M")))
    d.service("probe_db", "Probe database", 1, 0, "postgres_v2/DoSQL",
              _pg("SELECT 1, now()::text", fetch=True), "probe_result",
              post="db_ok = probe_result['command_response']['http_status'] == 200")
    d.end("end_heartbeat", "Probe done", 2, 0)
    d.flow("start_heartbeat", "probe_db")
    d.flow("probe_db", "end_heartbeat")
    return ConnectorModel("db-heartbeat", "Database Heartbeat",
                          "Timer start event + postgres connector. Seeded as draft: publish it to start the schedule.",
                          d, publish=False)


def partner_api_check() -> ConnectorModel:
    d = Diagram("partner-api-check", "Partner API Check",
                documentation="Calls a public echo API with GET and POST through the node-wire http connector.")
    d.lane("Submitters", 0, 1)
    d.start("start_check", "Check requested", 0, 0)
    d.user("enter_order", "Enter order reference", 1, 0, form="order-reference")
    d.service("get_status", "GET order status", 2, 0, "http/GetRequestV2", {
        "url": py("https://httpbin.org/get"),
        "params": "{'order': order_reference}",
    }, "status_response", post="status_code = status_response['command_response']['http_status']")
    d.service("post_update", "POST order update", 3, 0, "http/PostRequestV2", {
        "url": py("https://httpbin.org/post"),
        "data": "{'order': order_reference, 'quantity': quantity, 'status': 'shipped'}",
    }, "post_response", post="echoed_order = post_response['command_response']['body']['json']['order']")
    d.gateway("gw_echo", "Echo matches?", 4, 0)
    d.end("end_ok", "Partner in sync", 5, 0)
    d.manual("investigate", "Investigate mismatch", 5, 1)
    d.end("end_mismatch", "Mismatch logged", 6, 1)
    d.flow("start_check", "enter_order")
    d.flow("enter_order", "get_status")
    d.flow("get_status", "post_update")
    d.flow("post_update", "gw_echo")
    d.flow("gw_echo", "end_ok", "match", condition="echoed_order == order_reference and status_code == 200")
    d.flow("gw_echo", "investigate", "mismatch", default=True)
    d.flow("investigate", "end_mismatch")
    forms = {"order-reference": form("Order", {
        "order_reference": text("Order reference"), "quantity": integer("Quantity", minimum=1),
    }, ["order_reference", "quantity"])}
    return ConnectorModel("partner-api-check", "Partner API Check",
                          "HTTP connector scenario (GET + POST to httpbin.org). Requires internet egress.",
                          d, forms, needs_internet=True)


def all_connector_models() -> list[ConnectorModel]:
    return [customer_ledger(), db_heartbeat(), partner_api_check()]
