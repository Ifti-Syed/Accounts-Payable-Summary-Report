# /home/ifti/frappe-bench/apps/custom_accounts_payable_report/custom_accounts_payable_report/custom_accounts_payable_report/report/cvs_accounts_payable_summary_with_pdcs/cvs_accounts_payable_summary_with_pdcs.py

import json
from io import BytesIO

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import flt, nowdate

from erpnext.accounts.report.accounts_receivable_summary.accounts_receivable_summary import (
	AccountsReceivableSummary,
)

ARGS = {
	"account_type": "Payable",
	"naming_by": ["Buying Settings", "supp_master_name"],
}


def execute(filters=None):
	return CVSAccountsPayableSummaryWithPDCs(filters).run(ARGS)


class CVSAccountsPayableSummaryWithPDCs(AccountsReceivableSummary):
	def run(self, args):
		# Hard restriction: this report only ever covers Supplier payables,
		# regardless of what a user might otherwise pass in.
		self.filters.party_type = "Supplier"
		return super().run(args)

	def get_data(self, args):
		super().get_data(args)
		self.add_pdc_issued()

	def add_pdc_issued(self):
		# AccountsReceivableSummary.run() never calls set_defaults() on this
		# outer instance (only on the inner ReceivablePayableReport it builds),
		# so an unset Company filter would otherwise leave self.filters.company
		# empty here while the rest of the report has already fallen back to
		# the Global Defaults company.
		company = self.filters.get("company") or frappe.db.get_single_value(
			"Global Defaults", "default_company"
		)
		pdc_map = get_pdc_issued_map(company)
		for row in self.data:
			row.pdc_issued = flt(pdc_map.get(row.party), self.currency_precision)
			row.bal_outstanding = flt(row.total_due, self.currency_precision) - row.pdc_issued

	def get_columns(self):
		self.columns = []
		self.add_column(
			label=_("Party"),
			fieldname="party",
			fieldtype="Dynamic Link",
			options="party_type",
			width=180,
		)
		self.setup_ageing_columns()
		self.relabel_last_ageing_bucket()
		self.add_column(label=_("Total Amount"), fieldname="total_due")
		self.add_column(label=_("PDC Issued"), fieldname="pdc_issued")
		self.add_column(label=_("Bal Outstanding"), fieldname="bal_outstanding")

	def relabel_last_ageing_bucket(self):
		# setup_ageing_columns() labels the open-ended bucket "121-Above";
		# the business wants it shown as "121+" instead.
		last_range_value = 0
		for value in self.ranges:
			last_range_value = int(value) + 1

		last_fieldname = f"range{self.range_numbers[-1]}"
		for column in self.columns:
			if column["fieldname"] == last_fieldname:
				column["label"] = f"{last_range_value}+"


def get_pdc_issued_map(company=None):
	"""Sum of paid_amount on not-yet-cleared (post-dated) Payment Entries per Supplier."""
	# Query Builder works the same on Frappe v15 and v16 (v16 rejects SQL
	# function strings in get_all fields).
	pe = frappe.qb.DocType("Payment Entry")
	query = (
		frappe.qb.from_(pe)
		.select(pe.party, Sum(pe.paid_amount).as_("paid_amount"))
		.where(pe.docstatus != 2)
		.where(pe.posting_date > nowdate())
		.where(pe.party_type == "Supplier")
		.groupby(pe.party)
	)
	if company:
		query = query.where(pe.company == company)

	return {d.party: flt(d.paid_amount) for d in query.run(as_dict=True)}


@frappe.whitelist()
def download_excel_report(filters):
	"""Excel export with the Party column frozen (and header row locked)."""
	import openpyxl
	from openpyxl.styles import Alignment, Font, PatternFill
	from openpyxl.utils import get_column_letter

	if isinstance(filters, str):
		filters = frappe._dict(json.loads(filters))
	elif isinstance(filters, dict):
		filters = frappe._dict(filters)

	report = CVSAccountsPayableSummaryWithPDCs(filters)
	columns, data = report.run(ARGS)

	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = "AP Summary with PDCs"

	fieldnames = [col["fieldname"] for col in columns]
	headers = [col["label"] for col in columns]
	currency_fields = {col["fieldname"] for col in columns if col.get("fieldtype") == "Currency"}

	header_font = Font(bold=True, size=10)
	header_fill = PatternFill(start_color="BDD7EE", end_color="BDD7EE", fill_type="solid")
	header_align = Alignment(wrap_text=True, horizontal="center", vertical="center")
	right_align = Alignment(horizontal="right", vertical="center")
	left_align = Alignment(horizontal="left", vertical="center")

	ws.append(headers)
	ws.row_dimensions[1].height = 32
	for cell in ws[1]:
		cell.font = header_font
		cell.fill = header_fill
		cell.alignment = header_align

	for row_data in data:
		row_values = []
		for fn in fieldnames:
			val = row_data.get(fn)
			if fn in currency_fields and val is not None:
				row_values.append(flt(val, 2))
			else:
				row_values.append(val if val is not None else "")
		ws.append(row_values)

	col_widths = [len(str(h)) + 2 for h in headers]
	for row in ws.iter_rows(min_row=2):
		for col_idx, cell in enumerate(row):
			fn = fieldnames[col_idx] if col_idx < len(fieldnames) else ""
			cell.alignment = right_align if fn in currency_fields else left_align
			if cell.value is not None:
				col_widths[col_idx] = max(col_widths[col_idx], len(str(cell.value)) + 2)

	for col_idx, width in enumerate(col_widths, 1):
		ws.column_dimensions[get_column_letter(col_idx)].width = min(width, 40)

	# Freeze panes: header row locked, and everything frozen up to (not including)
	# column B - i.e. the Party column (A) stays visible while scrolling right.
	ws.freeze_panes = "B2"

	output = BytesIO()
	wb.save(output)
	output.seek(0)

	frappe.local.response.filecontent = output.read()
	frappe.local.response.type = "download"
	frappe.local.response.filename = "CVS_Accounts_Payable_Summary_with_PDCs.xlsx"
