// /home/ifti/frappe-bench/apps/custom_accounts_payable_report/custom_accounts_payable_report/custom_accounts_payable_report/report/cvs_accounts_payable_summary_with_pdcs/cvs_accounts_payable_summary_with_pdcs.js

frappe.query_reports["CVS Accounts Payable Summary with PDCs"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "report_date",
			label: __("Posting Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "ageing_based_on",
			label: __("Ageing Based On"),
			fieldtype: "Select",
			options: "Posting Date\nDue Date",
			default: "Posting Date",
		},
		{
			fieldname: "calculate_ageing_with",
			label: __("Calculate Ageing With"),
			fieldtype: "Select",
			options: "Report Date\nToday Date",
			default: "Report Date",
		},
		{
			fieldname: "range",
			label: __("Ageing Range"),
			fieldtype: "Data",
			default: "30, 60, 90, 120",
		},
		{
			fieldname: "finance_book",
			label: __("Finance Book"),
			fieldtype: "Link",
			options: "Finance Book",
		},
		{
			fieldname: "cost_center",
			label: __("Cost Center"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return frappe.db.get_link_options("Cost Center", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
			options: "Cost Center",
		},
		{
			fieldname: "party",
			label: __("Supplier"),
			fieldtype: "MultiSelectList",
			options: "Supplier",
			get_data: function (txt) {
				return frappe.db.get_link_options("Supplier", txt);
			},
		},
		{
			fieldname: "payment_terms_template",
			label: __("Payment Terms Template"),
			fieldtype: "Link",
			options: "Payment Terms Template",
		},
		{
			fieldname: "supplier_group",
			label: __("Supplier Group"),
			fieldtype: "Link",
			options: "Supplier Group",
		},
		{
			fieldname: "based_on_payment_terms",
			label: __("Based On Payment Terms"),
			fieldtype: "Check",
		},
		{
			fieldname: "for_revaluation_journals",
			label: __("Revaluation Journals"),
			fieldtype: "Check",
		},
	],

	after_datatable_render(datatable) {
		if (!datatable || datatable._freeze_applied) return;
		datatable._freeze_applied = true;

		const wrapper = datatable.wrapper;
		const bodyScrollable = datatable.bodyScrollable || wrapper.querySelector(".dt-scrollable");
		const header = datatable.header || wrapper.querySelector(".dt-header");
		if (!bodyScrollable || !header) return;

		// col 0: Sr No (auto-added by DataTable), col 1: Party -> freeze both
		// so the Party column stays visible while scrolling through ageing buckets.
		const frozenIndices = [0, 1];

		const offsets = {};
		let cumLeft = 0;
		frozenIndices.forEach((i) => {
			offsets[i] = cumLeft;
			const cell = header.querySelector(`.dt-cell--col-${i}`);
			cumLeft += cell ? cell.offsetWidth : 0;
		});

		const styleId = "dt-ap-pdc-freeze-style";
		const existing = document.getElementById(styleId);
		if (existing) existing.remove();
		const style = document.createElement("style");
		style.id = styleId;
		style.textContent = frozenIndices
			.map(
				(i) =>
					`.dt-cell--col-${i} { position: sticky !important; left: ${offsets[i]}px !important; z-index: 2 !important; background: #fff !important; }`
			)
			.join("\n");
		document.head.appendChild(style);

		bodyScrollable.addEventListener("scroll", function () {
			const scrollLeft = this.scrollLeft;
			frozenIndices.forEach((i) => {
				header.querySelectorAll(`.dt-cell--col-${i}`).forEach((cell) => {
					cell.style.transform = `translateX(${scrollLeft}px)`;
					cell.style.zIndex = "3";
					cell.style.position = "relative";
				});
			});
		});
	},

	onload(report) {
		report.page.add_inner_button(__("Export Excel (Party Frozen)"), () => {
			const filters = report.get_values();
			window.location = frappe.urllib.get_full_url(
				"/api/method/custom_accounts_payable_report.custom_accounts_payable_report.report.cvs_accounts_payable_summary_with_pdcs.cvs_accounts_payable_summary_with_pdcs.download_excel_report" +
					"?filters=" +
					encodeURIComponent(JSON.stringify(filters))
			);
		});
	},
};
