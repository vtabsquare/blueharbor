# BlueHarbor admin workspace update

This release rebuilds the admin application around six clear workspaces: Command Center, Buyer Compliance, Inventory & Catalogue, Orders & Shipping, Insights & Reports, and Administration.

Buyer verification now uses a dedicated case workspace. Staff can move between buyers, inspect company information, preview private documents, record a decision for each document, see missing requirements, assign ownership, make the final human decision, and send the buyer a separate message. Approval remains blocked until all current required documents have been approved.

Product, batch, warehouse, tank, order, trade-document, reporting, staff-access, notification, and audit functions remain available inside grouped workspace tabs. Price forms accept normal USD amounts. Stock adjustments use Add or Remove controls and show the resulting balance before saving. Every mutation still uses server validation and an audit reason.

Inventory alerts are deterministic. The backend checks low stock, expiry, allocated holds, and unusually large adjustments using saved records. Staff acknowledge and resolve these alerts in Insights & Reports.

The previous local model and Ollama adapter have been removed. This release performs no automated buyer verification or generated inventory analysis. Gemini integration is reserved for a later update.

Environment files are intentionally excluded from update packages. Keep the existing configured backend/.env on the target computer.

Run the application with python run_local.py. Validate code with npm run build, targeted lint, and the applicable backend tests before deployment.
