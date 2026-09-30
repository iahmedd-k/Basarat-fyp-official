# ADR-010: AAOIFI & KMI-30 Shariah Screening and Dividend Purification

## Status
**Accepted / Implemented**

## Context
A significant portion of investors on the Pakistan Stock Exchange (PSX) demand strict adherence to Islamic finance guidelines. However, standard financial platforms either omit Shariah screening altogether or only provide binary compliance tags without explaining the quantitative financial ratios or helping investors calculate required charity purification on non-compliant interest income earned by companies.

## Decision
Implement an automated **Dual-Standard Shariah Compliance & Dividend Purification Engine**:

1. **Screening Standard Compliance:**
   - Evaluates equities against both **KMI-30 (Meezan Pakistan Index)** and **AAOIFI (Accounting and Auditing Organization for Islamic Financial Institutions)** standards.
2. **Multi-Stage Quantitative Screening Criteria:**
   - **Stage 1: Core Business Activity:** Rejects conventional financial institutions (interest-based banks, conventional insurance), gambling, alcohol, tobacco, non-halal food, and adult entertainment.
   - **Stage 2: Debt-to-Total-Assets Ratio:** Total interest-bearing debt divided by Total Assets must be **$< 37\%$**.
   - **Stage 3: Non-Compliant Investments Ratio:** Non-Shariah compliant investments (interest-bearing deposits, bonds, conventional funds) divided by Total Assets must be **$< 33\%$**.
   - **Stage 4: Illiquid Assets Ratio:** Illiquid assets (tangible assets, inventory, plant & equipment) divided by Total Assets must be **$> 25\%$**.
   - **Stage 5: Non-Compliant Income Ratio:** Income derived from non-permissible sources (interest income, conventional securities) divided by Total Revenue must be **$< 5\%$**.
3. **Automated Dividend Purification Calculator:**
   - Formulates the exact non-compliant income deduction per dividend distribution:
     $$\text{Purification Amount per Share} = \text{Dividend per Share} \times \left( \frac{\text{Non-Compliant Income}}{\text{Total Revenue}} \right)$$
   - Directs the user on the precise rupee amount to donate to charity to purify their investment income.

## Alternatives Considered
- **Manual Static Lists from Brokerage Houses:** Rejected because static PDF lists become outdated between quarterly financial report filings.
- **Third-Party Commercial Islamic APIs:** Evaluated, but found to have minimal coverage of PSX small-cap and mid-cap equities.

## Consequences
- **Positive:** Automated, real-time compliance evaluation; complete transparency into debt and revenue ratios; practical mathematical tools for dividend purification.
- **Negative / Trade-off:** Requires regular updates of quarterly financial statements and balance sheet line items.

## Current Implementation
- Service logic in [app/services/shariah_service.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/shariah_service.py).
- Model in [app/models/shariah.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/models/shariah.py).
- Router in [app/api/v1/shariah.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/api/v1/shariah.py).
