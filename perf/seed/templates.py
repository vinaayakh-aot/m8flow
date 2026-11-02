"""The four Northwind Traders templates: diagrams, decision tables and forms.

Each template is a realistic back-office process. Together they exercise every
BPMN construct the m8flow host accepts and m8flow-core runs; see the coverage
matrix in perf/README.md. Lane names are the tenant's default groups, so tasks
are offered to group members without per-user configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bpmn_builder import Diagram, py

# Connector profile name the seed creates for postgres_v2 (points at the stack's own DB).
PG_PROFILE = py("default")


@dataclass
class Template:
    key: str
    name: str
    description: str
    category: str
    tags: list[str]
    diagram: Diagram
    dmn: tuple[str, str] | None = None  # (file name, xml)
    forms: dict[str, dict] = field(default_factory=dict)  # form base name -> {"schema":..., "uischema":...}

    @property
    def bpmn_file(self) -> str:
        return f"{self.key}.bpmn"


# ----------------------------------------------------------------------------- helpers
def form(title: str, properties: dict, required: list[str], order: list[str] | None = None,
         widgets: dict | None = None, description: str = "") -> dict:
    schema = {"title": title, "type": "object", "required": required, "properties": properties}
    if description:
        schema["description"] = description
    ui = {"ui:order": order or list(properties)}
    ui.update(widgets or {})
    return {"schema": schema, "uischema": ui}


def text(title, **kw):
    return {"type": "string", "title": title, **kw}


def enum(title, values, **kw):
    return {"type": "string", "title": title, "enum": values, **kw}


def number(title, **kw):
    return {"type": "number", "title": title, **kw}


def integer(title, **kw):
    return {"type": "integer", "title": title, **kw}


def boolean(title, **kw):
    return {"type": "boolean", "title": title, **kw}


def date(title, **kw):
    return {"type": "string", "format": "date", "title": title, **kw}


TEXTAREA = {"ui:widget": "textarea", "ui:options": {"rows": 3}}

APPROVAL_FORM = form(
    "Approval decision",
    {"outcome": enum("Decision", ["approve", "reject"]), "comments": text("Comments")},
    ["outcome"],
    widgets={"comments": TEXTAREA},
)


def dmn(decision_id: str, name: str, inputs: list[tuple[str, str, str]], outputs: list[tuple[str, str, str]],
        rules: list[tuple[str, list[str], list[str]]]) -> str:
    """inputs: (label, expression, typeRef); outputs: (label, name, typeRef); rules: (description, in, out)."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            '<definitions xmlns="https://www.omg.org/spec/DMN/20191111/MODEL/" '
            'xmlns:dmndi="https://www.omg.org/spec/DMN/20191111/DMNDI/" '
            'xmlns:dc="http://www.omg.org/spec/DMN/20180521/DC/" '
            f'id="Definitions_{decision_id}" name="{name}" namespace="http://camunda.org/schema/1.0/dmn">'
        ),
        f'  <decision id="{decision_id}" name="{name}">',
        f'    <decisionTable id="DecisionTable_{decision_id}" hitPolicy="UNIQUE">',
    ]
    for i, (label, expr, type_ref) in enumerate(inputs, 1):
        lines += [
            f'      <input id="Input_{i}" label="{label}">',
            (
                f'        <inputExpression id="InputExpression_{i}" typeRef="{type_ref}" expressionLanguage="python">'
                f"<text>{expr}</text></inputExpression>"
            ),
            "      </input>",
        ]
    for i, (label, out_name, type_ref) in enumerate(outputs, 1):
        lines.append(f'      <output id="Output_{i}" label="{label}" name="{out_name}" typeRef="{type_ref}" />')
    for r, (description, ins, outs) in enumerate(rules, 1):
        lines.append(f'      <rule id="Rule_{r}">')
        lines.append(f"        <description>{description}</description>")
        for i, entry in enumerate(ins, 1):
            lines.append(f'        <inputEntry id="Rule_{r}_in_{i}"><text>{_x(entry)}</text></inputEntry>')
        for i, entry in enumerate(outs, 1):
            lines.append(f'        <outputEntry id="Rule_{r}_out_{i}"><text>{_x(entry)}</text></outputEntry>')
        lines.append("      </rule>")
    lines += [
        "    </decisionTable>",
        "  </decision>",
        "  <dmndi:DMNDI>",
        "    <dmndi:DMNDiagram>",
        f'      <dmndi:DMNShape dmnElementRef="{decision_id}"><dc:Bounds height="80" width="180" x="160" y="100" /></dmndi:DMNShape>',
        "    </dmndi:DMNDiagram>",
        "  </dmndi:DMNDI>",
        "</definitions>",
    ]
    return "\n".join(lines) + "\n"


def _x(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ============================================================================ T1
def purchase_requisition() -> Template:
    d = Diagram(
        "purchase_requisition",
        "Purchase Requisition to Purchase Order",
        documentation="Procure-to-pay: an employee requests goods, approvals are routed by a DMN policy, "
        "budget is checked and committed in parallel, and a purchase order is sent to the supplier.",
    )
    d.lane("Submitters", 0, 1)
    d.lane("Approvers", 2, 4)
    d.lane("Administrators", 5, 6)
    d.partner_pool("Participant_supplier", "Supplier")
    po_msg = d.message("Message_purchase_order", "purchase_order")

    d.start("start_requisition", "Purchase needed", 0, 0)
    d.user("submit_requisition", "Submit purchase requisition", 1, 0, form="purchase-requisition",
           instructions="Describe what you need. Requests up to $500 are approved automatically.")
    d.script("prepare_requisition", "Prepare requisition record", 2, 0,
             "total = round(float(quantity) * float(unit_price), 2)\n"
             "requisition = {'item': item_description, 'category': category, 'quantity': quantity, "
             "'unit_price': unit_price, 'total': total, 'vendor': vendor_name}\n"
             "requisition_status = 'submitted'\nreminders_sent = 0")
    d.data_object("requisition", "Requisition", 2, 1)
    d.data_output("prepare_requisition", "requisition")
    d.rule("determine_approval_route", "Determine approval route", 3, 0, "approval_route")
    d.annotate("note_policy", "approval_route.dmn: total and category decide auto / manager / director", 3, 1,
               "determine_approval_route")
    d.gateway("gw_approval_level", "Approval level?", 4, 0)

    d.user("manager_approval", "Manager approval", 5, 2, form="approval-decision",
           instructions="Requisition for {{ quantity }} x {{ item_description }} from {{ vendor_name }}: "
                        "${{ total }} ({{ category }}).",
           post="manager_outcome = outcome")
    d.data_input("manager_approval", "requisition")
    d.boundary("b_manager_reminder", "Every 12h", "manager_approval", kind="timer",
               timer=("cycle", py("R2/PT12H")), interrupting=False, slot=0)
    d.boundary("b_manager_overdue", "3 days", "manager_approval", kind="timer",
               timer=("duration", py("P3D")), slot=1)
    d.script("remind_manager", "Log approval reminder", 5, 4,
             "reminders_sent += 1")
    d.end("end_reminder", "Reminder logged", 6, 4)
    d.gateway("gw_manager_decision", "Manager decision?", 6, 2)
    d.gateway("gw_director_merge", None, 7, 3)
    d.user("director_approval", "Director approval", 8, 3, form="approval-decision",
           instructions="High-value or overdue requisition: ${{ total }} for {{ item_description }}.")
    d.gateway("gw_director_decision", "Director decision?", 9, 3)
    d.gateway("gw_rejected", None, 9, 2)
    d.script("record_rejection", "Record rejection", 10, 2, "requisition_status = 'rejected'")
    d.end("end_rejected", "Requisition rejected", 11, 2, kind="terminate")

    d.gateway("gw_approved", "Approved", 10, 0)
    d.gateway("gw_checks", None, 11, 5, kind="parallel")
    d.script("check_budget", "Check departmental budget", 12, 5,
             "budget_remaining = 250000\nbudget_ok = total <= budget_remaining")
    d.service("ensure_ledger", "Ensure commitment ledger", 12, 6, "postgres_v2/DoSQL", {
        "m8flow_profile": PG_PROFILE,
        "database_connection_str": None,
        "schema": "{'sql': 'CREATE TABLE IF NOT EXISTS perf_purchase_commitments (id serial PRIMARY KEY, "
                  "item text, category text, total numeric, created_at timestamptz DEFAULT now())'}",
    }, "ledger_ready")
    d.service("record_commitment", "Record budget commitment", 13, 6, "postgres_v2/DoSQL", {
        "m8flow_profile": PG_PROFILE,
        "database_connection_str": None,
        "schema": "{'sql': 'INSERT INTO perf_purchase_commitments (item, category, total) VALUES (%s, %s, %s) "
                  "RETURNING id', 'values': [item_description, category, total], 'fetch_results': True}",
    }, "commitment", post="commitment_id = commitment['command_response']['body']['body'][0][0]")
    d.gateway("gw_checks_join", None, 14, 5, kind="parallel")
    d.group("group_checks", "Budget control", 11, 5, 4, 2)
    d.script("create_po", "Create purchase order", 15, 5,
             "po_number = 'PO-' + str(commitment_id).zfill(6)\nrequisition_status = 'ordered'")
    d.send("send_po", "Send PO to supplier", 16, 5, po_msg)
    d.manual("receive_goods", "Receive goods", 17, 5,
             instructions="Confirm {{ quantity }} x {{ item_description }} arrived for {{ po_number }}.")
    d.end("end_received", "Goods received", 18, 5)
    d.message_flow("MessageFlow_po", "Purchase order", "send_po", "Participant_supplier", po_msg)
    d.message_flow("MessageFlow_delivery", "Delivery note", "Participant_supplier", "receive_goods")

    d.flow("start_requisition", "submit_requisition")
    d.flow("submit_requisition", "prepare_requisition")
    d.flow("prepare_requisition", "determine_approval_route")
    d.flow("determine_approval_route", "gw_approval_level")
    d.flow("gw_approval_level", "gw_approved", "auto", default=True)
    d.flow("gw_approval_level", "manager_approval", "needs approval", condition="approval_level != 'auto'")
    d.flow("b_manager_reminder", "remind_manager")
    d.flow("remind_manager", "end_reminder")
    d.flow("b_manager_overdue", "gw_director_merge", "overdue")
    d.flow("manager_approval", "gw_manager_decision")
    d.flow("gw_manager_decision", "gw_rejected", "rejected", condition="outcome == 'reject'")
    d.flow("gw_manager_decision", "gw_director_merge", "director", condition="approval_level == 'director'")
    d.flow("gw_manager_decision", "gw_approved", "approved", default=True)
    d.flow("gw_director_merge", "director_approval")
    d.flow("director_approval", "gw_director_decision")
    d.flow("gw_director_decision", "gw_rejected", "rejected", condition="outcome == 'reject'")
    d.flow("gw_director_decision", "gw_approved", "approved", default=True)
    d.flow("gw_rejected", "record_rejection")
    d.flow("record_rejection", "end_rejected")
    d.flow("gw_approved", "gw_checks")
    d.flow("gw_checks", "check_budget")
    d.flow("gw_checks", "ensure_ledger")
    d.flow("ensure_ledger", "record_commitment")
    d.flow("check_budget", "gw_checks_join")
    d.flow("record_commitment", "gw_checks_join")
    d.flow("gw_checks_join", "create_po")
    d.flow("create_po", "send_po")
    d.flow("send_po", "receive_goods")
    d.flow("receive_goods", "end_received")

    decision = dmn(
        "approval_route", "Approval route",
        inputs=[("Total", "total", "number"), ("Category", "category", "string")],
        outputs=[("Approval level", "approval_level", "string"), ("Budget code", "budget_code", "string")],
        rules=[
            ("Small purchases are auto-approved", ["? <= 500", ""], ['"auto"', '"OPEX-GEN"']),
            ("Hardware above 500 needs a director", ["? > 500", '"IT Hardware"'], ['"director"', '"CAPEX-IT"']),
            ("Large purchases need a director", ["? > 10000", ""], ['"director"', '"CAPEX-GEN"']),
            ("Everything else goes to the manager", ["500 < ? <= 10000", ""], ['"manager"', '"OPEX-GEN"']),
        ],
    )
    forms = {
        "purchase-requisition": form(
            "Purchase requisition",
            {
                "item_description": text("Item"),
                "category": enum("Category", ["IT Hardware", "Software", "Office Supplies", "Marketing Services",
                                              "Facilities"]),
                "quantity": integer("Quantity", minimum=1),
                "unit_price": number("Unit price (USD)", minimum=0),
                "vendor_name": text("Preferred vendor"),
                "needed_by": date("Needed by"),
                "justification": text("Business justification"),
            },
            ["item_description", "category", "quantity", "unit_price", "vendor_name"],
            widgets={"justification": TEXTAREA},
        ),
        "approval-decision": APPROVAL_FORM,
    }
    return Template("purchase-requisition", "Purchase Requisition to Purchase Order",
                    "Procure-to-pay with DMN approval routing, SLA timers, parallel budget control "
                    "(PostgreSQL ledger via node-wire) and a supplier collaboration.",
                    "Procurement", ["procurement", "dmn", "timers", "postgres"], d,
                    ("approval_route.dmn", decision), forms)


# ============================================================================ T2
def employee_onboarding() -> Template:
    d = Diagram(
        "employee_onboarding",
        "Employee Onboarding",
        documentation="HR, IT and the hiring manager prepare a new hire's first day: documents, accounts, "
                      "equipment and a welcome meeting.",
    )
    d.lane("Administrators", 0, 1)
    d.lane("Approvers", 2, 2)
    d.lane("Support", 3, 5)
    d.lane("Submitters", 6, 6)
    docs_signal = d.signal("Signal_documents_submitted", "documents_submitted")
    backorder = d.escalation("Escalation_laptop_backorder", "Laptop backorder", "LAPTOP_BACKORDER")

    d.start("start_onboarding", "Offer accepted", 0, 0)
    d.user("enter_new_hire", "Enter new hire details", 1, 0, form="new-hire")
    d.rule("plan_onboarding", "Plan onboarding", 2, 0, "onboarding_plan",
           post="systems = base_systems.split(',')\nlaptop_in_stock = department != 'Sales'")
    d.gateway("gw_start", None, 3, 0, kind="parallel")

    # HR waits for the new hire's documents (signal) or chases them after two days.
    d.gateway("gw_wait_documents", "Documents in?", 4, 0, kind="eventBased")
    d.catch("catch_documents", "Documents submitted", 5, 0, kind="signal", ref=docs_signal)
    d.catch("timer_documents", "2 days", 5, 1, kind="timer", timer=("duration", py("P2D")))
    d.user("verify_documents", "Verify documents", 6, 0, form="verify-documents")
    d.manual("chase_documents", "Collect documents in person", 6, 1)
    d.gateway("gw_documents_done", None, 7, 0)

    # New hire submits paperwork and signals HR.
    d.user("submit_documents", "Submit onboarding documents", 4, 6, form="new-hire-documents")
    d.throw("throw_documents", "Documents submitted", 5, 6, kind="signal", ref=docs_signal)

    # IT provisioning sub-process: loop over systems, escalate a laptop backorder.
    d.container("it_provisioning", "IT provisioning", 4, 3, 5, 2)
    d.start("sp_it_start", None, 4, 3, parent="it_provisioning")
    # Loop state lives only on this branch: a parallel join merges branch data, and a
    # stale copy from another branch would otherwise overwrite it.
    d.script("prepare_provisioning", "Prepare provisioning", 5, 3, "system_index = 0\nprovisioned = []",
             parent="it_provisioning")
    d.script("provision_accounts", "Provision system account", 6, 3,
             "provisioned.append(systems[system_index])\nsystem_index += 1",
             loop=("system_index < len(systems)", 10), parent="it_provisioning")
    d.gateway("gw_laptop_stock", "Laptop in stock?", 7, 3, parent="it_provisioning")
    d.end("sp_it_end", None, 8, 3, parent="it_provisioning")
    d.throw("throw_backorder", "Laptop backorder", 7, 4, kind="escalation", ref=backorder, parent="it_provisioning")
    d.end("sp_it_end_backorder", None, 8, 4, parent="it_provisioning")
    d.boundary("b_backorder", "Backorder", "it_provisioning", kind="escalation", ref=backorder,
               interrupting=False)
    d.user("order_laptop", "Order replacement laptop", 5, 5, form="order-laptop")
    d.end("end_laptop_ordered", "Laptop ordered", 6, 5)

    d.gateway("gw_equipment", "Equipment needed?", 9, 3, kind="inclusive")
    d.manual("issue_laptop", "Issue laptop", 10, 3)
    d.manual("issue_phone", "Issue phone", 10, 4)
    d.task("issue_badge", "Print access badge", 10, 5)
    d.gateway("gw_equipment_join", None, 11, 3, kind="inclusive")

    d.gateway("gw_ready", None, 12, 0, kind="parallel")
    d.catch("wait_start_date", "Start date", 13, 0, kind="timer",
            timer=("date", "start_date + 'T09:00:00+00:00'"))
    d.script("mark_ready", "Mark workspace ready", 14, 0, "workspace_ready = len(provisioned) == len(systems)")
    d.catch("catch_ready", "Workspace ready", 15, 0, kind="conditional", condition="workspace_ready == True")
    d.user("welcome_meeting", "Day-one welcome meeting", 16, 2, form="welcome-checklist",
           instructions="Welcome {{ full_name }} ({{ role }}, {{ department }}). Accounts: {{ provisioned }}.")
    d.end("end_onboarded", "Employee onboarded", 17, 2)
    d.annotate("note_documents", "The new hire's submission throws documents_submitted, releasing HR's event gateway",
               2, 6, "submit_documents")

    d.flow("start_onboarding", "enter_new_hire")
    d.flow("enter_new_hire", "plan_onboarding")
    d.flow("plan_onboarding", "gw_start")
    d.flow("gw_start", "gw_wait_documents")
    d.flow("gw_start", "it_provisioning")
    d.flow("gw_start", "submit_documents")
    d.flow("gw_wait_documents", "catch_documents")
    d.flow("gw_wait_documents", "timer_documents")
    d.flow("catch_documents", "verify_documents")
    d.flow("timer_documents", "chase_documents")
    d.flow("verify_documents", "gw_documents_done")
    d.flow("chase_documents", "gw_documents_done")
    d.flow("gw_documents_done", "gw_ready")
    d.flow("submit_documents", "throw_documents")
    d.flow("throw_documents", "gw_ready")
    d.flow("sp_it_start", "prepare_provisioning")
    d.flow("prepare_provisioning", "provision_accounts")
    d.flow("provision_accounts", "gw_laptop_stock")
    d.flow("gw_laptop_stock", "sp_it_end", "in stock", default=True)
    d.flow("gw_laptop_stock", "throw_backorder", "backorder", condition="needs_laptop and not laptop_in_stock")
    d.flow("throw_backorder", "sp_it_end_backorder")
    d.flow("b_backorder", "order_laptop")
    d.flow("order_laptop", "end_laptop_ordered")
    d.flow("it_provisioning", "gw_equipment")
    d.flow("gw_equipment", "issue_laptop", "laptop", condition="needs_laptop == True")
    d.flow("gw_equipment", "issue_phone", "phone", condition="needs_phone == True")
    d.flow("gw_equipment", "issue_badge", "badge", default=True)
    d.flow("issue_laptop", "gw_equipment_join")
    d.flow("issue_phone", "gw_equipment_join")
    d.flow("issue_badge", "gw_equipment_join")
    d.flow("gw_equipment_join", "gw_ready")
    d.flow("gw_ready", "wait_start_date")
    d.flow("wait_start_date", "mark_ready")
    d.flow("mark_ready", "catch_ready")
    d.flow("catch_ready", "welcome_meeting")
    d.flow("welcome_meeting", "end_onboarded")

    decision = dmn(
        "onboarding_plan", "Onboarding plan",
        inputs=[("Department", "department", "string"), ("Employment type", "employment_type", "string")],
        outputs=[("Systems", "base_systems", "string"), ("Buddy programme", "buddy_programme", "boolean")],
        rules=[
            ("Contractors get the minimum", ["", '"Contractor"'], ['"email,vpn"', "False"]),
            ("Engineering", ['"Engineering"', ""], ['"email,vpn,hris,github,jira,ci"', "True"]),
            ("Sales", ['"Sales"', ""], ['"email,vpn,hris,crm,cpq"', "True"]),
            ("Everyone else", ["", ""], ['"email,vpn,hris"', "True"]),
        ],
    )
    forms = {
        "new-hire": form(
            "New hire",
            {
                "full_name": text("Full name"),
                "email": text("Personal email", format="email"),
                "department": enum("Department", ["Engineering", "Sales", "Marketing", "Finance", "Operations"]),
                "role": text("Job title"),
                "employment_type": enum("Employment type", ["Full-time", "Contractor"]),
                "start_date": date("Start date"),
                "needs_laptop": boolean("Needs a laptop", default=True),
                "needs_phone": boolean("Needs a phone", default=False),
            },
            ["full_name", "department", "role", "employment_type", "start_date"],
        ),
        "new-hire-documents": form(
            "Onboarding documents",
            {
                "id_document_provided": boolean("Photo ID uploaded"),
                "tax_form_provided": boolean("Tax form completed"),
                "bank_details_provided": boolean("Bank details provided"),
            },
            ["id_document_provided", "tax_form_provided", "bank_details_provided"],
        ),
        "verify-documents": form(
            "Verify documents",
            {"documents_verified": boolean("Documents verified"), "hr_notes": text("Notes")},
            ["documents_verified"],
            widgets={"hr_notes": TEXTAREA},
        ),
        "order-laptop": form(
            "Order replacement laptop",
            {"laptop_vendor": text("Vendor"), "laptop_eta_days": integer("ETA (days)", minimum=0)},
            ["laptop_vendor", "laptop_eta_days"],
        ),
        "welcome-checklist": form(
            "Welcome checklist",
            {"buddy_assigned": boolean("Buddy assigned"), "first_week_plan": text("First-week plan")},
            ["buddy_assigned"],
            widgets={"first_week_plan": TEXTAREA},
        ),
    }
    return Template("employee-onboarding", "Employee Onboarding",
                    "Parallel HR / IT / new-hire onboarding with signals, an event-based gateway, a looping "
                    "provisioning sub-process with escalation, inclusive equipment routing and date timers.",
                    "Human Resources", ["hr", "signals", "escalation", "inclusive-gateway"], d,
                    ("onboarding_plan.dmn", decision), forms)


# ============================================================================ T3
def insurance_claim() -> Template:
    d = Diagram(
        "insurance_claim",
        "Insurance Claim Handling",
        documentation="First notice of loss through triage, investigation, authority checks and a "
                      "transactional payout.",
    )
    d.lane("Submitters", 0, 0)
    d.lane("Support", 1, 3)
    d.lane("Approvers", 4, 4)
    d.lane("Administrators", 5, 7)
    fraud = d.error("Error_fraud_confirmed", "Fraud confirmed", "FRAUD_CONFIRMED")
    over_authority = d.escalation("Escalation_over_authority", "Over adjuster authority", "OVER_AUTHORITY")

    d.start("start_claim", "Loss reported", 0, 0)
    d.user("report_claim", "Report claim", 1, 0, form="claim-report")
    d.rule("triage_claim", "Triage claim", 2, 0, "claim_triage", post="settlement_amount = estimated_amount")
    d.gateway("gw_triage", "Triage?", 3, 0)

    d.user("collect_information", "Collect supporting documents", 4, 1, form="claim-information",
           loop=("not documents_complete", 3),
           instructions="Policy {{ policy_number }}: request any missing documents from the policyholder.")
    d.user("assess_damage", "Assess damage", 5, 1, form="damage-assessment",
           post="settlement_amount = assessed_amount")

    # Human tasks stay outside the containers: m8flow-core only raises work items for
    # top-level tasks (validate.py enforces this), so each container wraps the
    # automated part of a step and keeps its event semantics.
    d.user("review_evidence", "Review evidence", 4, 2, form="fraud-investigation")
    d.container("investigation", "Fraud ruling", 5, 2, 4, 2)
    d.start("sp_inv_start", None, 5, 2, parent="investigation")
    d.script("record_findings", "Record findings", 6, 2,
             "fraud_score = 90 if fraud_confirmed else 10\nclaim_status = 'investigated'", parent="investigation")
    d.gateway("gw_fraud", "Fraud?", 7, 2, parent="investigation")
    d.end("sp_inv_end", None, 8, 2, parent="investigation")
    d.end("end_fraud", "Fraud confirmed", 7, 3, kind="error", ref=fraud, parent="investigation")
    d.boundary("b_fraud", "Fraud", "investigation", kind="error", ref=fraud)
    d.script("record_denial", "Record fraud denial", 5, 4, "claim_status = 'denied_fraud'")
    d.end("end_denied", "Claim denied", 6, 4)

    d.gateway("gw_assessed", None, 9, 1)
    d.container("authority_check", "Adjuster authority check", 10, 1, 3, 2)
    d.start("sp_auth_start", None, 10, 1, parent="authority_check")
    d.gateway("gw_authority", "Within authority?", 11, 1, parent="authority_check")
    d.end("sp_auth_end", None, 12, 1, parent="authority_check")
    d.end("end_over_authority", "Over authority", 11, 2, kind="escalation", ref=over_authority,
          parent="authority_check")
    d.boundary("b_over_authority", "Escalated", "authority_check", kind="escalation", ref=over_authority)
    d.user("senior_review", "Senior adjuster review", 10, 4, form="senior-review",
           post="settlement_amount = approved_amount if outcome == 'approve' else settlement_amount")
    d.gateway("gw_senior", "Senior decision?", 11, 4)
    d.end("end_rejected", "Claim rejected", 12, 4)

    d.gateway("gw_settle", None, 13, 5)
    d.user("approve_payment", "Release payment", 14, 5, form="payment-release",
           instructions="Release ${{ settlement_amount }} for policy {{ policy_number }}.")
    d.container("payout", "Settlement payout", 15, 5, 5, 2, transaction=True)
    d.start("tx_start", None, 15, 5, parent="payout")
    d.script("reserve_funds", "Reserve funds", 16, 5, "reserve_id = 'RSV-' + policy_number", parent="payout")
    d.script("execute_transfer", "Execute bank transfer", 17, 5,
             "transfer_status = 'sent' if payment_successful else 'bounced'", parent="payout")
    d.gateway("gw_payment", "Paid?", 18, 5, parent="payout")
    d.end("tx_end", None, 19, 5, parent="payout")
    d.end("tx_cancel", "Payment failed", 18, 6, kind="cancel", parent="payout")
    d.boundary("b_payment_cancelled", "Cancelled", "payout", kind="cancel")
    d.script("release_reserve", "Release reserve", 15, 7, "claim_status = 'payment_failed'")
    d.end("end_payment_failed", "Payout cancelled", 16, 7)
    d.script("close_claim", "Close claim", 20, 5, "claim_status = 'paid'")
    d.end("end_paid", "Claim paid", 21, 5)

    d.flow("start_claim", "report_claim")
    d.flow("report_claim", "triage_claim")
    d.flow("triage_claim", "gw_triage")
    d.flow("gw_triage", "gw_settle", "fast track", condition="triage == 'fast_track'")
    d.flow("gw_triage", "collect_information", "standard", default=True)
    d.flow("gw_triage", "review_evidence", "investigate", condition="triage == 'investigate'")
    d.flow("collect_information", "assess_damage")
    d.flow("assess_damage", "gw_assessed")
    d.flow("review_evidence", "investigation")
    d.flow("sp_inv_start", "record_findings")
    d.flow("record_findings", "gw_fraud")
    d.flow("gw_fraud", "end_fraud", "fraud", condition="fraud_confirmed == True")
    d.flow("gw_fraud", "sp_inv_end", "genuine", default=True)
    d.flow("investigation", "gw_assessed")
    d.flow("b_fraud", "record_denial")
    d.flow("record_denial", "end_denied")
    d.flow("gw_assessed", "authority_check")
    d.flow("sp_auth_start", "gw_authority")
    d.flow("gw_authority", "end_over_authority", "over limit", condition="settlement_amount > authority_limit")
    d.flow("gw_authority", "sp_auth_end", "within limit", default=True)
    d.flow("authority_check", "gw_settle")
    d.flow("b_over_authority", "senior_review")
    d.flow("senior_review", "gw_senior")
    d.flow("gw_senior", "end_rejected", "rejected", condition="outcome == 'reject'")
    d.flow("gw_senior", "gw_settle", "approved", default=True)
    d.flow("gw_settle", "approve_payment")
    d.flow("approve_payment", "payout")
    d.flow("tx_start", "reserve_funds")
    d.flow("reserve_funds", "execute_transfer")
    d.flow("execute_transfer", "gw_payment")
    d.flow("gw_payment", "tx_cancel", "failed", condition="payment_successful == False")
    d.flow("gw_payment", "tx_end", "paid", default=True)
    d.flow("b_payment_cancelled", "release_reserve")
    d.flow("release_reserve", "end_payment_failed")
    d.flow("payout", "close_claim")
    d.flow("close_claim", "end_paid")

    decision = dmn(
        "claim_triage", "Claim triage",
        inputs=[("Estimated amount", "estimated_amount", "number"), ("Prior claims", "prior_claims", "integer"),
                ("Police report", "police_report_filed", "boolean")],
        outputs=[("Triage", "triage", "string"), ("Authority limit", "authority_limit", "number")],
        rules=[
            ("Repeat claimants are investigated", ["", "? >= 3", ""], ['"investigate"', "10000"]),
            ("Large losses without a police report", ["? > 50000", "", "False"], ['"investigate"', "25000"]),
            ("Small clean claims are fast-tracked", ["? <= 2500", "", ""], ['"fast_track"', "2500"]),
            ("Everything else is standard", ["", "", ""], ['"standard"', "25000"]),
        ],
    )
    forms = {
        "claim-report": form(
            "Report a claim",
            {
                "policy_number": text("Policy number"),
                "claim_type": enum("Claim type", ["Auto", "Property"]),
                "incident_date": date("Incident date"),
                "estimated_amount": number("Estimated loss (USD)", minimum=0),
                "police_report_filed": boolean("Police report filed", default=False),
                "prior_claims": integer("Claims in the last 3 years", minimum=0, default=0),
                "description": text("What happened?"),
            },
            ["policy_number", "claim_type", "incident_date", "estimated_amount", "prior_claims"],
            widgets={"description": TEXTAREA},
        ),
        "claim-information": form(
            "Supporting documents",
            {"documents_complete": boolean("All documents received"), "document_notes": text("Notes")},
            ["documents_complete"],
        ),
        "damage-assessment": form(
            "Damage assessment",
            {"assessed_amount": number("Assessed amount (USD)", minimum=0), "assessment_notes": text("Notes")},
            ["assessed_amount"],
            widgets={"assessment_notes": TEXTAREA},
        ),
        "fraud-investigation": form(
            "Fraud investigation",
            {"fraud_confirmed": boolean("Fraud confirmed"), "findings": text("Findings")},
            ["fraud_confirmed"],
            widgets={"findings": TEXTAREA},
        ),
        "senior-review": form(
            "Senior adjuster review",
            {"outcome": enum("Decision", ["approve", "reject"]),
             "approved_amount": number("Approved amount (USD)", minimum=0), "comments": text("Comments")},
            ["outcome", "approved_amount"],
        ),
        "payment-release": form(
            "Release payment",
            {"payment_successful": boolean("Payment succeeded", default=True), "payment_reference": text("Bank reference")},
            ["payment_successful"],
        ),
    }
    return Template("insurance-claim", "Insurance Claim Handling",
                    "FNOL with DMN triage, a looping document request, a fraud ruling sub-process with "
                    "error events, an escalation to a senior adjuster and a transactional payout with cancel.",
                    "Insurance", ["claims", "error-events", "escalation", "transaction"], d,
                    ("claim_triage.dmn", decision), forms)


# ============================================================================ T4
def it_incident() -> Template:
    d = Diagram(
        "it_incident",
        "IT Incident Management",
        documentation="ITIL-style incident management: DMN prioritisation, SLA reminders, change approval, "
                      "a resolution signal and reporter confirmation.",
    )
    d.lane("Submitters", 0, 1)
    d.lane("Support", 2, 4)
    d.lane("Approvers", 5, 5)
    resolved = d.signal("Signal_incident_resolved", "incident_resolved")
    d.process_io([("incident_input", "Incident channel")], [("incident_outcome", "Incident outcome")])

    d.start("start_incident", "Incident reported", 0, 0)
    d.user("report_incident", "Report incident", 1, 0, form="incident-report",
           pre="incident_input = 'self-service portal'")
    d.rule("prioritize_incident", "Prioritise incident", 2, 0, "incident_priority",
           post="sla_reminders = 0\nsla_breached = False")
    d.gateway("gw_fanout", None, 3, 0, kind="parallel")

    d.gateway("gw_await", "Resolved or SLA?", 4, 0, kind="eventBased")
    d.catch("catch_resolved", "Incident resolved", 5, 0, kind="signal", ref=resolved)
    d.catch("timer_sla", "SLA elapsed", 5, 1, kind="timer", timer=("duration", "'PT' + str(sla_hours) + 'H'"))
    d.script("post_sla_breach", "Post SLA breach notice", 6, 1, "sla_breached = True")
    d.gateway("gw_comms", None, 7, 0)

    d.user("diagnose", "Diagnose incident", 4, 2, form="diagnosis",
           instructions="{{ priority }} incident on {{ service }}: {{ summary }} ({{ affected_users }} users).")
    d.boundary("b_sla_reminder", "Every 30 min", "diagnose", kind="timer", timer=("cycle", py("R3/PT30M")),
               interrupting=False)
    d.script("remind_assignee", "Remind assignee", 4, 3, "sla_reminders += 1")
    d.end("end_reminded", "Reminder sent", 5, 3)
    d.gateway("gw_resolution", "Resolution path?", 5, 2)
    d.user("approve_change", "Approve emergency change", 6, 5, form="change-approval")
    d.gateway("gw_change", "Change approved?", 7, 5)
    d.manual("apply_workaround", "Apply workaround", 8, 4)
    d.gateway("gw_fix", None, 9, 2)
    d.manual("implement_fix", "Implement fix", 10, 2,
             instructions="Implement the {{ resolution_type }} for {{ root_cause }}.")
    d.throw("throw_resolved", "Incident resolved", 11, 2, kind="signal", ref=resolved)

    d.gateway("gw_join", None, 12, 0, kind="parallel")
    d.data_object("incident_record", "Incident record", 13, 1)
    d.user("confirm_resolution", "Confirm resolution", 13, 0, form="resolution-confirmation")
    d.script("close_incident", "Close incident", 14, 0,
             "incident_record = {'priority': priority, 'service': service, 'root_cause': root_cause, "
             "'sla_breached': sla_breached}\n"
             "incident_outcome = 'closed' if confirmed else 'closed_unconfirmed'")
    d.data_output("close_incident", "incident_record")
    d.end("end_closed", "Incident closed", 15, 0)
    d.annotate("note_signal", "Resolution throws incident_resolved; the reporter's event gateway catches it "
                              "unless the SLA timer fires first", 11, 3, "throw_resolved")

    d.flow("start_incident", "report_incident")
    d.flow("report_incident", "prioritize_incident")
    d.flow("prioritize_incident", "gw_fanout")
    d.flow("gw_fanout", "gw_await")
    d.flow("gw_fanout", "diagnose")
    d.flow("gw_await", "catch_resolved")
    d.flow("gw_await", "timer_sla")
    d.flow("catch_resolved", "gw_comms")
    d.flow("timer_sla", "post_sla_breach")
    d.flow("post_sla_breach", "gw_comms")
    d.flow("gw_comms", "gw_join")
    d.flow("b_sla_reminder", "remind_assignee")
    d.flow("remind_assignee", "end_reminded")
    d.flow("diagnose", "gw_resolution")
    d.flow("gw_resolution", "approve_change", "change", condition="resolution_type == 'change_required'")
    d.flow("gw_resolution", "gw_fix", "fix", default=True)
    d.flow("approve_change", "gw_change")
    d.flow("gw_change", "apply_workaround", "rejected", condition="outcome == 'reject'")
    d.flow("gw_change", "gw_fix", "approved", default=True)
    d.flow("apply_workaround", "gw_fix")
    d.flow("gw_fix", "implement_fix")
    d.flow("implement_fix", "throw_resolved")
    d.flow("throw_resolved", "gw_join")
    d.flow("gw_join", "confirm_resolution")
    d.flow("confirm_resolution", "close_incident")
    d.flow("close_incident", "end_closed")

    decision = dmn(
        "incident_priority", "Incident priority",
        inputs=[("Impact", "impact", "string"), ("Urgency", "urgency", "string")],
        outputs=[("Priority", "priority", "string"), ("SLA hours", "sla_hours", "integer")],
        rules=[
            ("Critical", ['"High"', '"High"'], ['"P1"', "4"]),
            ("High", ['"High"', ""], ['"P2"', "8"]),
            ("High urgency", ["", '"High"'], ['"P2"', "8"]),
            ("Medium", ['"Medium"', '"Medium"'], ['"P3"', "24"]),
            ("Low", ["", ""], ['"P4"', "72"]),
        ],
    )
    forms = {
        "incident-report": form(
            "Report an incident",
            {
                "summary": text("Summary"),
                "service": enum("Affected service", ["Email", "VPN", "ERP", "Website", "Laptop"]),
                "impact": enum("Impact", ["High", "Medium", "Low"]),
                "urgency": enum("Urgency", ["High", "Medium", "Low"]),
                "affected_users": integer("Users affected", minimum=1, default=1),
            },
            ["summary", "service", "impact", "urgency"],
        ),
        "diagnosis": form(
            "Diagnosis",
            {"root_cause": text("Root cause"),
             "resolution_type": enum("Resolution", ["fix", "workaround", "change_required"])},
            ["root_cause", "resolution_type"],
        ),
        "change-approval": APPROVAL_FORM,
        "resolution-confirmation": form(
            "Confirm resolution",
            {"confirmed": boolean("The issue is resolved", default=True),
             "satisfaction": integer("Satisfaction (1-5)", minimum=1, maximum=5), "feedback": text("Feedback")},
            ["confirmed"],
            widgets={"feedback": TEXTAREA},
        ),
    }
    return Template("it-incident", "IT Incident Management",
                    "Incident management with DMN prioritisation, an SLA race on an event-based gateway, "
                    "reminder timers, emergency change approval and process data inputs/outputs.",
                    "IT Service Management", ["itsm", "signals", "sla", "event-gateway"], d,
                    ("incident_priority.dmn", decision), forms)


def all_templates() -> list[Template]:
    return [purchase_requisition(), employee_onboarding(), insurance_claim(), it_incident()]
