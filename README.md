# PandoraV2 — Sales and Inventory Management System

> **PandoraV2** is a separate copy of Pandora for the final lab. It adds a REST API (7 tables),
> OpenStreetMap geocoding (external API), a Leaflet.js map, and Branch, Customer and Warranty claim tables.
> See [DEPLOY.md](DEPLOY.md) for PythonAnywhere deployment and where each lab requirement lives,
> and [SETUP.md](SETUP.md) for local setup.

> **Project status:** 🟢 Feature-complete — final fixes and presentation prep  
> **Project period:** October 21 – November 20, 2026  
> **Team size:** 3 members  
> **Last updated:** November 23, 2026  

Pandora is a Sales and Inventory Management System designed to help a store record sales, track stock levels, manage suppliers and restocking, and produce reports. Its goal is to make inventory movements accurate, efficient, and easy to monitor.

**Important:** This README is our project **progress tracker**. A box is checked only when the feature exists in the code and is covered by the test suite or was verified in the app. Update the checkboxes, status table, and progress log as work is finished.

---

## 📌 Project Goals

- Manage products, categories, prices, and inventory quantities.
- Record sales, compute totals and change, and generate receipts.
- Automatically deduct stock after successful sales.
- Record purchases/restocking from suppliers and automatically add received stock.
- Show reorder-level or low-stock alerts.
- Manage suppliers and view their transaction history.
- Generate sales, inventory, product-movement, and profit/loss reports.
- Export reports to PDF or Excel.
- Support role-based access and database backups.

## 🛠️ Tech Stack (as built)

| Area | Technology |
| --- | --- |
| Backend | Python 3.12+, Django 6.1 |
| REST API | Django REST Framework (`/api/`, 7 tables) |
| Frontend | Django templates, custom CSS (`theme.css`, light/dark), vanilla JavaScript, installable PWA |
| Maps / external API | Leaflet.js + OpenStreetMap tiles, OpenStreetMap Nominatim geocoding |
| Database | MySQL 8.4+ locally; SQLite on PythonAnywhere (`PANDORA_DB_ENGINE=sqlite`) |
| Authentication | Django Authentication and Groups, django-allauth |
| Reports / exports | ReportLab (PDF) |
| Development tools | VS Code, Git, GitHub |
| Diagrams | diagrams.net (Draw.io) |
| Hosting | PythonAnywhere |

> Changes from the original proposal: Bootstrap was replaced by a custom stylesheet; Excel export (OpenPyXL) was not built, so reports export to PDF only; SQLite was added because PythonAnywhere's MySQL is older than Django 6.1 supports.

## 👥 Team Responsibilities

| Team member | Primary responsibility | Main deliverable |
| --- | --- | --- |
| **Member 1:** Charles Joaquin N. Alabastro | Database, backend, login, access control, integration | Database models and Crow's Foot ERD |
| **Member 2:** John Emmanuel P. Pablico | Frontend, products, inventory interface, sales | User interface, receipts, Use Case Diagram |
| **Member 3:** Daven Rupert Y. Villar | Suppliers, purchasing, reports, exports | Restocking, reports, Data Flow Diagram (DFD) |

**Shared responsibilities:** testing, documentation, reviewing changes, troubleshooting, PowerPoint, and live demonstration.

## 📅 One-Month Milestones

| Week | Dates | Target | Status |
| --- | --- | --- | --- |
| **Week 1** | Oct 21–27 | Setup, database design, diagrams, mockups | ✅ Completed |
| **Week 2** | Oct 28–Nov 3 | User roles, product and supplier management | ✅ Completed |
| **Week 3** | Nov 4–10 | Sales, receipts, purchases, automatic stock updates | ✅ Completed |
| **Week 4** | Nov 11–17 | Reports, export, backup, security, testing | 🟡 Done except Excel export |
| **Final** | Nov 18–20 | Documentation, slides, rehearsal, final fixes | 🟡 In progress |
| **V2 (final lab)** | Nov 21–23 | REST API, geocoding, Leaflet map, branches, customers, warranty claims | ✅ Completed |

**Milestone statuses:** ⬜ Not started / not confirmed · 🟡 In progress · ✅ Completed · 🔴 Blocked

## ✅ Development Checklist

### Week 1 — Planning and System Design (Oct 21–27)

**Member 1 — Database & Backend**
- [x] Create the Django project and GitHub repository.
- [x] Configure the development environment and MySQL connection.
- [x] Design a normalized database schema with primary and foreign keys.
- [x] Draw the ERD with Crow's Foot notation and relationship cardinalities.

**Member 2 — Frontend & Sales**
- [x] Draft user interface mockups (login, dashboard, products, checkout).
- [x] Set up the base HTML layout and styling (custom CSS instead of Bootstrap).
- [x] Draw the Use Case Diagram for Administrator, Cashier, and Inventory Clerk.

**Member 3 — Purchasing & Reports**
- [x] Identify fields needed for supplier, purchase, and report records.
- [x] Draw the Data Flow Diagram (DFD).
- [x] Prepare realistic sample products, suppliers, and transactions.

**Week 1 outcome:** Agreed models, diagrams, mockups, and a running starter project.

### Week 2 — User Accounts, Products, and Suppliers (Oct 28–Nov 3)

**Member 1 — Database & Backend**
- [x] Create Django models, migrations, and database relationships.
- [x] Implement login/logout and unique user accounts.
- [x] Set up role-based permissions for Administrator, Cashier, and Inventory Clerk.

**Member 2 — Frontend & Sales**
- [x] Build the dashboard/navigation layout.
- [x] Implement product and category add/view/edit/delete interfaces.
- [x] Display current stock, search/filter products, and show low-stock alerts.

**Member 3 — Purchasing & Reports**
- [x] Implement supplier add/view/edit/delete features.
- [x] Create supplier detail pages and prepare transaction-history views.
- [x] Coordinate purchase form fields with Member 1's models.

**Week 2 outcome:** Authorized users can log in and manage products and suppliers.

### Week 3 — Sales and Restocking (Nov 4–10)

**Member 1 — Database & Backend**
- [x] Implement reliable inventory update rules for sales and restocking.
- [x] Prevent sales from creating negative stock.
- [x] Ensure each transaction and its stock updates succeed or fail together (database transaction).
- [x] Integrate the sales and purchasing modules.

**Member 2 — Frontend & Sales**
- [x] Build the sales checkout form/cart.
- [x] Calculate subtotal, applicable taxes (if any), total, amount received, and change.
- [x] Save completed sales and their items.
- [x] Generate a printable sales receipt.

**Member 3 — Purchasing & Reports**
- [x] Record supplier purchases and received items.
- [x] Automatically increase inventory when stock is received.
- [x] Generate purchase-order or stock-in records.
- [x] Display supplier purchase history.

**Week 3 outcome:** Demonstrate a complete **sale → stock deduction → restock → stock increase** cycle.

### Week 4 — Reports, Security, and Testing (Nov 11–17)

**Member 1 — Database & Backend**
- [x] Verify permissions for critical actions and sensitive records.
- [x] Set up and test a database backup and restore procedure.
- [x] Fix integration bugs and validate stock movement history.

**Member 2 — Frontend & Sales**
- [x] Add daily, weekly, and monthly sales summaries to the interface.
- [x] Add record/report filters (date, product type, transaction status where applicable).
- [x] Improve usability, error messages, and responsive styling.

**Member 3 — Purchasing & Reports**
- [x] Create inventory status reports.
- [x] Create fast-moving and slow-moving product reports.
- [x] Create profit/loss summaries using recorded sales and cost data.
- [x] Implement PDF report exports.
- [ ] Implement Excel report exports *(not built)*.

**All members**
- [x] Test the complete transaction flow with sample data.
- [x] Fix high-priority bugs and verify totals and stock quantities.
- [x] Check that each role can access only authorized features.

**Week 4 outcome:** Integrated system with working reporting, exports, and security checks.

### Final Days — Presentation and Submission (Nov 18–20)

*Not verifiable from the code — team to check these off.*

- [ ] Update and verify the ERD, Use Case Diagram, and DFD against the implemented system.
- [ ] Capture screenshots and sample input/output forms (receipt, stock-in record, reports).
- [ ] Document the final tech stack and cite reasons/references for each choice.
- [ ] Prepare the PowerPoint presentation.
- [ ] Rehearse the complete operation within **45 minutes**.
- [x] Prepare a working demo dataset (`python manage.py seed_demo_data`: computer store, 2 years of history).
- [ ] Perform a final test on the deployed site.

### V2 — Final Lab Additions (Nov 21–23)

- [x] REST API with CRUD on 7 tables (categories, products, suppliers, expense categories, branches, customers, warranty claims).
- [x] External API: OpenStreetMap Nominatim geocoding of supplier, branch and customer addresses.
- [x] Leaflet.js + OpenStreetMap map of suppliers, branches and customers (`/map/`).
- [x] Branch, Customer and Warranty claim tables with pages.
- [x] Operating expenses and expense categories (used in profit/loss).
- [x] Installable PWA with app icons and offline page.
- [x] Demo data reseeded as a computer store with branches, customers and warranty claims.
- [x] PythonAnywhere deployment guide ([DEPLOY.md](DEPLOY.md)).
- [x] Database CHECKs for valid latitude/longitude (migration 0006, `test_coordinates.py`).

## 🗃️ Database Entities (as built)

- **Users / Roles** — logins and access permissions.
- **Categories** — product categories.
- **Suppliers** — company and contact details.
- **Products** — product code, name, category, supplier (if applicable), prices, stock, reorder level.
- **Sales** — date, cashier, totals, payment information.
- **Sale_Items** — products, quantities, and selling prices for each sale.
- **Purchases** — supplier, dates, and purchasing/receiving details.
- **Purchase_Items** — products, quantities, and unit costs received.
- **Stock_Movements** — auditable additions and deductions, with references to transactions.
- **Expense_Categories / Operating_Expenses** — business expenses for profit/loss.
- **Branches** — store locations with coordinates.
- **Customers** — customer details with coordinates.
- **Warranty_Claims** — claims tied to products that were sold.

> Keep sales and purchase line items separate from transaction headers to support normalization. Preserve historical transaction prices instead of relying only on a product's current price.

## 🧪 Acceptance Tests / Demo Checklist

Use these tests to confirm a feature truly works before checking off a milestone.

- [x] An authorized user can log in and access only their allowed pages.
- [x] An authorized user can create, update, and search for a product.
- [x] Inventory shows correct stock before a sale.
- [x] Completing a sale decreases stock by the quantity sold.
- [x] Trying to sell more units than available is rejected.
- [x] A completed sale produces a receipt with correct totals and change.
- [x] Recording received stock increases inventory by the received quantity.
- [x] A purchase or stock-in record is saved with supplier and items.
- [x] A product at/below its reorder level triggers a low-stock indication.
- [x] Daily, weekly, and monthly reports show correct totals.
- [x] Fast/slow-moving and profit/loss figures match the sample data.
- [x] PDF exports open correctly. *(Excel not built.)*
- [x] A backup can be restored successfully.

### Example Full-Cycle Demo

1. Log in as an administrator or appropriate staff member.
2. Create a supplier and a product with **20 units** in stock.
3. Sell **3 units**; verify the receipt and new stock of **17**.
4. Receive **10 units** from the supplier; verify new stock of **27**.
5. Review sales, purchase, inventory movement, and report records.
6. Export a report and demonstrate role-based restrictions.

## 🎤 Presentation Plan (Maximum 45 Minutes)

| Segment | Time | Lead |
| --- | --- | --- |
| Introduction and tech stack with references | 5 min | Member 1 |
| ERD, Use Case Diagram, and DFD | 10 min | All members |
| Live system demonstration | 20 min | Members 2 and 3, Member 1 supports |
| Reports, testing, and security | 5 min | All members |
| Questions and answers | 5 min | All members |
| **Total** | **45 min** | |

## 📝 Progress Log

Add a row whenever a task is completed, a blocker occurs, or an important decision is made.

| Date | Member | Work completed / decision | Status / blocker |
| --- | --- | --- | --- |
| 2026-10-21 | Team | Created initial one-month project tracker | Planning |
| 2026-11-20 | Team | Pandora feature-complete: products, suppliers, sales, purchases, stock movements, reports, PDF export, roles, backup/restore | Done (Excel export dropped) |
| 2026-11-23 | Daven | PandoraV2 created for the final lab: REST API, Nominatim geocoding, Leaflet map, branches, customers, warranty claims, PWA | Done |
| 2026-11-23 | Daven | New Pandora logo and PWA icons | Done |
| 2026-11-23 | Daven | Demo data reseeded as a computer store (48 products, 2 years of history, branches, customers, warranty claims) | Done |
| 2026-11-23 | Daven | Latitude/longitude range CHECK constraints (migration 0006) | Done — tests pass on SQLite and MySQL |

## 🚧 Issues and Blockers

| Issue | Owner | Next action | Status |
| --- | --- | --- | --- |
| Excel export was never built | Member 3 | Add an OpenPyXL export, or say "PDF only" in the presentation | Open |
| `test_coordinates.py` errors on SQLite (schema editor inside a transaction) | Daven | Fixed: preflight tests no longer open a schema editor | Resolved |
| PythonAnywhere free tier may block Nominatim | Daven | Allowlist `nominatim.openstreetmap.org`, or enter coordinates by hand | Open |
| PythonAnywhere MySQL older than 8.4 | Daven | Use SQLite there (`PANDORA_DB_ENGINE=sqlite`) | Resolved |

## 🤝 Team Workflow

1. Agree on shared model names and fields before starting dependent features.
2. Work on separate Git branches (for example: `feature/database`, `feature/sales`, `feature/purchases-reports`).
3. Make small commits with clear messages; review changes before merging into `main`.
4. Run migrations and test the full project after integrating a feature.
5. Update this README and record blockers at each group check-in.
6. Do a joint integration test at the end of each week.

## 📚 Tech References (for Final Presentation)

- [Django documentation](https://docs.djangoproject.com/en/stable/)
- [Python documentation](https://docs.python.org/3/)
- [MySQL documentation](https://dev.mysql.com/doc/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Leaflet.js](https://leafletjs.com/)
- [OpenStreetMap Nominatim](https://nominatim.org/release-docs/latest/)
- [ReportLab](https://docs.reportlab.com/)
- [Django authentication and authorization](https://docs.djangoproject.com/en/stable/topics/auth/)

---

**Pandora — Sales and Inventory Management System**  
*Built by a team of three. Update this file as development progresses.*
