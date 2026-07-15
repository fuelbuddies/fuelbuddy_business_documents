# Copyright (c) 2026, Fuelbuddy and contributors
# For license information, please see license.txt

"""Business Documentation endpoints for the document panel embedded on the deal
doctypes (Lead/Opportunity/Quotation/Customer/Finance Dossier), plus the daily
expiry sweep. Moved here from the business_doc_* Server Script fixtures so the
logic lives in the app (see patches.remove_server_scripts)."""

import frappe

from fuelbuddy_business_documents.fuelbuddy_business_documents.doctype.business_documentation.business_documentation import (
	documents_enforced,
)

_FIELDS = [
	"name", "reference_doctype", "reference_name", "document_type", "document_number",
	"attachment", "status", "expiry", "uploaded_by", "upload_date", "current_version", "remarks",
]


@frappe.whitelist()
def get_docs(reference_doctype, reference_name):
	"""Documents uploaded on the reference itself ("own") plus everywhere else on
	its deal chain ("linked"): the party (Customer/Lead), the Opportunity, the
	Quotation and the Finance Dossier all show each other's documents."""
	related = []
	if reference_doctype == "Customer":
		for q in frappe.get_all("Quotation", filters={"quotation_to": "Customer", "party_name": reference_name}, pluck="name"):
			related.append(("Quotation", q))
		for o in frappe.get_all("Opportunity", filters={"opportunity_from": "Customer", "party_name": reference_name}, pluck="name"):
			related.append(("Opportunity", o))
		for fd in frappe.get_all("Finance Dossier", filters={"finance_dossier_from": "Customer", "id": reference_name}, pluck="name"):
			related.append(("Finance Dossier", fd))
		lead = frappe.db.get_value("Customer", reference_name, "lead_name")
		if lead:
			related.append(("Lead", lead))
	elif reference_doctype == "Lead":
		for o in frappe.get_all("Opportunity", filters={"opportunity_from": "Lead", "party_name": reference_name}, pluck="name"):
			related.append(("Opportunity", o))
		for q in frappe.get_all("Quotation", filters={"quotation_to": "Lead", "party_name": reference_name}, pluck="name"):
			related.append(("Quotation", q))
		for fd in frappe.get_all("Finance Dossier", filters={"finance_dossier_from": "Lead", "id": reference_name}, pluck="name"):
			related.append(("Finance Dossier", fd))
		for c in frappe.get_all("Customer", filters={"lead_name": reference_name}, pluck="name"):
			related.append(("Customer", c))
	elif reference_doctype == "Opportunity":
		for q in frappe.get_all("Quotation", filters={"custom_opportunity_from": reference_name}, pluck="name"):
			related.append(("Quotation", q))
		for qi in frappe.get_all("Quotation Item", filters={"prevdoc_docname": reference_name, "prevdoc_doctype": "Opportunity"}, fields=["parent"]):
			related.append(("Quotation", qi.parent))
		for fd in frappe.get_all("Finance Dossier", filters={"finance_dossier_from": "Opportunity", "id": reference_name}, pluck="name"):
			related.append(("Finance Dossier", fd))
		opp = frappe.db.get_value("Opportunity", reference_name, ["opportunity_from", "party_name"], as_dict=True)
		if opp and opp.opportunity_from and opp.party_name:
			related.append((opp.opportunity_from, opp.party_name))
	elif reference_doctype == "Quotation":
		q = frappe.db.get_value("Quotation", reference_name, ["quotation_to", "party_name", "custom_opportunity_from"], as_dict=True)
		if q and q.quotation_to and q.party_name:
			related.append((q.quotation_to, q.party_name))
		if q and q.custom_opportunity_from:
			related.append(("Opportunity", q.custom_opportunity_from))
		for qi in frappe.get_all("Quotation Item", filters={"parent": reference_name, "prevdoc_doctype": "Opportunity"}, fields=["prevdoc_docname"]):
			if qi.prevdoc_docname:
				related.append(("Opportunity", qi.prevdoc_docname))
	elif reference_doctype == "Finance Dossier":
		fd = frappe.db.get_value("Finance Dossier", reference_name, ["finance_dossier_from", "id"], as_dict=True)
		if fd and fd.finance_dossier_from and fd.id:
			related.append((fd.finance_dossier_from, fd.id))
			# walk the deal chain so the FD can review documents uploaded on the
			# Quotation's Opportunity (and the underlying Lead/Customer) too.
			if fd.finance_dossier_from == "Quotation":
				q = frappe.db.get_value("Quotation", fd.id,
					["quotation_to", "party_name", "custom_opportunity_from", "opportunity"], as_dict=True)
				if q:
					opp = q.custom_opportunity_from or q.opportunity
					if opp:
						related.append(("Opportunity", opp))
					if q.quotation_to and q.party_name:
						related.append((q.quotation_to, q.party_name))

	seen, uniq = set(), []
	for dt, nm in related:
		if (dt, nm) == (reference_doctype, reference_name) or (dt, nm) in seen:
			continue
		seen.add((dt, nm))
		uniq.append((dt, nm))

	own = frappe.get_all(
		"Business Documentation",
		filters={"reference_doctype": reference_doctype, "reference_name": reference_name},
		fields=_FIELDS, order_by="document_type asc",
	)
	linked = []
	for dt, nm in uniq:
		linked += frappe.get_all(
			"Business Documentation",
			filters={"reference_doctype": dt, "reference_name": nm},
			fields=_FIELDS, order_by="document_type asc",
		)
	return {"own": own, "linked": linked}


@frappe.whitelist()
def add_version(tracker, file_url, note=None):
	"""Append a new version to an existing Business Documentation and reset it to
	PENDING_APPROVAL. On a submitted reference only the Finance Dossier's own panel
	may re-version (ignore_validate bypasses the upload lock there)."""
	doc = frappe.get_doc("Business Documentation", tracker)
	ref_submitted = (
		doc.reference_doctype and doc.reference_name
		and frappe.db.get_value(doc.reference_doctype, doc.reference_name, "docstatus") == 1
	)
	if ref_submitted and documents_enforced() and doc.reference_doctype != "Finance Dossier":
		frappe.throw(f"Cannot add a new version on a submitted {doc.reference_doctype}.")
	if ref_submitted:
		doc.flags.ignore_validate = 1
	new_ver = (doc.current_version or 1) + 1
	doc.append("versions", {
		"version_no": new_ver, "attachment": file_url,
		"uploaded_by": frappe.session.user, "upload_date": frappe.utils.now_datetime(),
		"change_note": note,
	})
	doc.current_version = new_ver
	doc.attachment = file_url
	doc.status = "PENDING_APPROVAL"
	doc.reviewed_by = None
	doc.reviewed_on = None
	doc.save()
	return {"name": doc.name, "current_version": new_ver}


@frappe.whitelist()
def force_save(reference_doctype, reference_name, attachment, document_type=None,
		document_number=None, expiry=None):
	"""Create a Business Documentation (first version). On a submitted reference
	only the Finance Dossier's own panel may upload (ignore_validate bypasses the
	upload lock there)."""
	ref_submitted = (
		reference_doctype and reference_name
		and frappe.db.get_value(reference_doctype, reference_name, "docstatus") == 1
	)
	if ref_submitted and documents_enforced() and reference_doctype != "Finance Dossier":
		frappe.throw(f"Cannot upload documents on a submitted {reference_doctype}.")
	now = frappe.utils.now_datetime()
	doc = frappe.get_doc({
		"doctype": "Business Documentation",
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
		"document_type": document_type,
		"document_number": document_number,
		"attachment": attachment,
		"expiry": expiry or None,
		"status": "PENDING_APPROVAL",
		"uploaded_by": frappe.session.user,
		"upload_date": now,
		"current_version": 1,
		"versions": [{
			"version_no": 1, "attachment": attachment,
			"uploaded_by": frappe.session.user, "upload_date": now,
			"change_note": "Initial upload",
		}],
	})
	if ref_submitted:
		doc.flags.ignore_validate = 1
	doc.insert()
	return {"name": doc.name}


def expire_documents():
	"""Daily scheduler task: mark documents past their expiry date EXPIRED."""
	today = frappe.utils.today()
	names = frappe.get_all(
		"Business Documentation",
		filters=[["expiry", "<", today], ["status", "not in", ["EXPIRED", "REJECTED"]]],
		pluck="name",
	)
	for n in names:
		frappe.db.set_value("Business Documentation", n, "status", "EXPIRED")
