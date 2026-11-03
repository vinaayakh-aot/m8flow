"""Named paths through each template/connector model.

A path maps a task's BPMN id to the form answers a user submits for it. A list
of answers is consumed one per occurrence (standard loops). Every path names
the end event(s) it must reach, so the same data drives:

* validate.py -- runs each path in-process on the m8flow-core engine, and
* load.py     -- starts real instances over HTTP and completes their tasks.

Branches only a timer can reach (overdue approval, document chase, SLA breach,
a future start time) live in TIMER_PATHS; suite.py runs them on the seeded
models. The templates use timers of seconds, so these paths take under a
minute. Answer values "@now+<n>s" become an ISO timestamp when submitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Path:
    name: str
    answers: dict[str, dict | list[dict]]
    expect_end: tuple[str, ...]
    weight: int = 1  # relative frequency in a load mix
    # Leave a task open: "seen:<task id>" until that task has appeared, or
    # "after:<seconds>" once it has been pending that long. Lets a timer win a race.
    hold: dict[str, str] = field(default_factory=dict)
    # BPMN element ids (events, scripts, ...) that must have completed.
    expect_completed: tuple[str, ...] = ()


APPROVE = {"outcome": "approve", "comments": "Looks good"}
REJECT = {"outcome": "reject", "comments": "Not in budget"}

PURCHASE_REQUISITION = [
    Path("auto-approved office supplies", {
        "submit_requisition": {"item_description": "A4 paper", "category": "Office Supplies", "quantity": 10,
                               "unit_price": 4.5, "vendor_name": "Paper Co"},
        "receive_goods": {},
    }, ("end_received",), weight=5),
    Path("manager-approved software", {
        "submit_requisition": {"item_description": "Design tool licence", "category": "Software", "quantity": 3,
                               "unit_price": 400, "vendor_name": "SoftSupply"},
        "manager_approval": APPROVE,
        "receive_goods": {},
    }, ("end_received",), weight=3),
    Path("director-approved hardware", {
        "submit_requisition": {"item_description": "Workstation", "category": "IT Hardware", "quantity": 2,
                               "unit_price": 1500, "vendor_name": "HW Direct"},
        "manager_approval": APPROVE,
        "director_approval": APPROVE,
        "receive_goods": {},
    }, ("end_received",), weight=2),
    Path("manager-rejected marketing", {
        "submit_requisition": {"item_description": "Billboard", "category": "Marketing Services", "quantity": 1,
                               "unit_price": 8000, "vendor_name": "AdCo"},
        "manager_approval": REJECT,
    }, ("end_rejected",)),
]

EMPLOYEE_ONBOARDING = [
    Path("engineering full-time", {
        "enter_new_hire": {"full_name": "Ada Byron", "email": "ada@example.test", "department": "Engineering",
                           "role": "Backend Engineer", "employment_type": "Full-time", "start_at": "2026-01-05T09:00:00+00:00",
                           "needs_laptop": True, "needs_phone": True},
        "submit_documents": {"id_document_provided": True, "tax_form_provided": True, "bank_details_provided": True},
        "verify_documents": {"documents_verified": True},
        "issue_laptop": {}, "issue_phone": {},
        "welcome_meeting": {"buddy_assigned": True, "first_week_plan": "Pairing"},
    }, ("end_onboarded",), weight=3),
    Path("sales laptop backorder", {
        "enter_new_hire": {"full_name": "Sam Seller", "email": "sam@example.test", "department": "Sales",
                           "role": "Account Executive", "employment_type": "Full-time", "start_at": "2026-01-05T09:00:00+00:00",
                           "needs_laptop": True, "needs_phone": False},
        "submit_documents": {"id_document_provided": True, "tax_form_provided": True, "bank_details_provided": True},
        "verify_documents": {"documents_verified": True},
        "order_laptop": {"laptop_vendor": "HW Direct", "laptop_eta_days": 5},
        "issue_laptop": {},
        "welcome_meeting": {"buddy_assigned": True},
    }, ("end_onboarded", "end_laptop_ordered"), weight=2),
    Path("contractor badge only", {
        "enter_new_hire": {"full_name": "Casey Contract", "email": "casey@example.test", "department": "Operations",
                           "role": "Consultant", "employment_type": "Contractor", "start_at": "2026-01-05T09:00:00+00:00",
                           "needs_laptop": False, "needs_phone": False},
        "submit_documents": {"id_document_provided": True, "tax_form_provided": True, "bank_details_provided": True},
        "verify_documents": {"documents_verified": True},
        "issue_badge": {},
        "welcome_meeting": {"buddy_assigned": False},
    }, ("end_onboarded",)),
]

_CLAIM = {"policy_number": "POL-1001", "claim_type": "Auto", "incident_date": "2026-09-01",
          "police_report_filed": True, "prior_claims": 0, "description": "Rear-ended at a junction"}
PAID = {"payment_successful": True, "payment_reference": "BANK-1"}

INSURANCE_CLAIM = [
    Path("fast-track small claim", {
        "report_claim": {**_CLAIM, "estimated_amount": 1200},
        "approve_payment": PAID,
    }, ("end_paid",), weight=4),
    Path("standard claim with document loop", {
        "report_claim": {**_CLAIM, "estimated_amount": 8000},
        "collect_information": [{"documents_complete": False}, {"documents_complete": True}],
        "assess_damage": {"assessed_amount": 7000},
        "approve_payment": PAID,
    }, ("end_paid",), weight=3),
    Path("over authority, senior approves", {
        "report_claim": {**_CLAIM, "claim_type": "Property", "estimated_amount": 40000},
        "collect_information": {"documents_complete": True},
        "assess_damage": {"assessed_amount": 40000},
        "senior_review": {"outcome": "approve", "approved_amount": 35000},
        "approve_payment": PAID,
    }, ("end_paid",)),
    Path("over authority, senior rejects", {
        "report_claim": {**_CLAIM, "claim_type": "Property", "estimated_amount": 60000},
        "collect_information": {"documents_complete": True},
        "assess_damage": {"assessed_amount": 60000},
        "senior_review": {"outcome": "reject", "approved_amount": 0},
    }, ("end_rejected",)),
    Path("fraud confirmed", {
        "report_claim": {**_CLAIM, "estimated_amount": 9000, "prior_claims": 3},
        "review_evidence": {"fraud_confirmed": True, "findings": "Staged accident"},
    }, ("end_denied",)),
    Path("genuine after investigation, payout fails", {
        "report_claim": {**_CLAIM, "estimated_amount": 9000, "prior_claims": 4},
        "review_evidence": {"fraud_confirmed": False},
        "approve_payment": {"payment_successful": False},
    }, ("end_payment_failed",)),
]

_INCIDENT = {"summary": "VPN drops every few minutes", "service": "VPN", "affected_users": 40}
CONFIRMED = {"confirmed": True, "satisfaction": 4}

IT_INCIDENT = [
    Path("P2 fixed", {
        "report_incident": {**_INCIDENT, "impact": "High", "urgency": "Medium"},
        "diagnose": {"root_cause": "Gateway firmware", "resolution_type": "fix"},
        "implement_fix": {},
        "confirm_resolution": CONFIRMED,
    }, ("end_closed",), weight=4),
    Path("P1 emergency change approved", {
        "report_incident": {**_INCIDENT, "impact": "High", "urgency": "High"},
        "diagnose": {"root_cause": "Certificate expired", "resolution_type": "change_required"},
        "approve_change": APPROVE,
        "implement_fix": {},
        "confirm_resolution": CONFIRMED,
    }, ("end_closed",), weight=2),
    Path("P3 change rejected, workaround", {
        "report_incident": {**_INCIDENT, "impact": "Medium", "urgency": "Medium"},
        "diagnose": {"root_cause": "Client config", "resolution_type": "change_required"},
        "approve_change": REJECT,
        "apply_workaround": {},
        "implement_fix": {},
        "confirm_resolution": {"confirmed": False, "feedback": "Still flaky"},
    }, ("end_closed",)),
]

CUSTOMER_LEDGER = [
    Path("ledger entry", {"enter_payment": {"customer": "Acme", "amount": 125.5, "invoice": "INV-1"}},
         ("end_entry",)),
]

PARTNER_API_CHECK = [
    Path("echo in sync", {"enter_order": {"order_reference": "ORD-1", "quantity": 2}}, ("end_ok",)),
]

BY_KEY: dict[str, list[Path]] = {
    "purchase-requisition": PURCHASE_REQUISITION,
    "employee-onboarding": EMPLOYEE_ONBOARDING,
    "insurance-claim": INSURANCE_CLAIM,
    "it-incident": IT_INCIDENT,
    "customer-ledger": CUSTOMER_LEDGER,
    "partner-api-check": PARTNER_API_CHECK,
}


# --------------------------------------------------------------------------- timer paths
# Each path leaves a task open (hold) so the timer wins the race it models.
TIMER_PATHS: dict[str, list[Path]] = {
    "purchase-requisition": [
        Path("approval overdue escalates to director (boundary timers)", {
            "submit_requisition": {"item_description": "Design tool licence", "category": "Software", "quantity": 3,
                                   "unit_price": 400, "vendor_name": "SoftSupply"},
            "director_approval": APPROVE,
            "receive_goods": {},
        }, ("end_received", "end_reminder"),
            hold={"manager_approval": "seen:director_approval"},
            expect_completed=("b_manager_reminder", "remind_manager", "b_manager_overdue")),
    ],
    "employee-onboarding": [
        Path("documents chased after timeout (event-based gateway timer)", {
            "enter_new_hire": {"full_name": "Tim Ing", "email": "tim@example.test", "department": "Engineering",
                               "role": "SRE", "employment_type": "Full-time", "start_at": "2026-01-05T09:00:00+00:00", "needs_laptop": True, "needs_phone": False},
            "chase_documents": {},
            "submit_documents": {"id_document_provided": True, "tax_form_provided": True,
                                 "bank_details_provided": True},
            "issue_laptop": {},
            "welcome_meeting": {"buddy_assigned": True},
        }, ("end_onboarded",),
            hold={"submit_documents": "seen:chase_documents"},
            expect_completed=("timer_documents", "chase_documents")),
        Path("start date in the future (timer date)", {
            "enter_new_hire": {"full_name": "Fu Ture", "email": "fu@example.test", "department": "Sales",
                               "role": "AE", "employment_type": "Contractor", "start_at": "@now+20s", "needs_laptop": False, "needs_phone": False},
            "submit_documents": {"id_document_provided": True, "tax_form_provided": True,
                                 "bank_details_provided": True},
            "verify_documents": {"documents_verified": True},
            "issue_badge": {},
            "welcome_meeting": {"buddy_assigned": False},
        }, ("end_onboarded",), expect_completed=("wait_start_date", "catch_ready")),
    ],
    "it-incident": [
        Path("SLA breached before diagnosis (event-based gateway + cycle boundary)", {
            "report_incident": {**_INCIDENT, "impact": "High", "urgency": "High"},
            "diagnose": {"root_cause": "Gateway firmware", "resolution_type": "fix"},
            "implement_fix": {},
            "confirm_resolution": CONFIRMED,
        }, ("end_closed", "end_reminded"),
            hold={"diagnose": "after:45"},
            expect_completed=("timer_sla", "post_sla_breach", "b_sla_reminder", "remind_assignee")),
    ],
}
