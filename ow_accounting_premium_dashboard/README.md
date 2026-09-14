# Premium Accounting Dashboard

An Odoo 19 Accounting app dashboard for finance teams. It brings current-period performance, company-currency balances, invoice follow-up, and recent activity into one responsive view.

## Included

- Income, expenses, and net result for the current month, quarter, year, or all time. Amounts use Odoo's signed company-currency fields, so refunds and vendor credits reduce the appropriate total.
- Open receivables and payables, plus posted cash and bank balances.
- Six-month income and expense chart.
- Overdue customer invoices and vendor bills due in the next seven days.
- Recent posted invoices and bills with payment status and direct links to the source records.
- Clickable KPI cards, manual refresh, and automatic refresh every two minutes.

## Installation

Add `ow_accounting_premium_dashboard` to the Odoo addons path, update the Apps list, and install **Premium Accounting Dashboard**. It appears as its own top-level **Finance Studio** app for users with accounting read or invoice access.

The dashboard uses Odoo's normal model access rights and company record rules. Users see only accounting data they are allowed to access.
