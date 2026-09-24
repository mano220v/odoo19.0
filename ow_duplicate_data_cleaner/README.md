# Duplicate Data Cleaner Pro

Duplicate Data Cleaner Pro finds, reviews, and safely consolidates duplicate records in Odoo 19.

## Main features

- Rules for any stored Odoo model and field
- Exact and fuzzy matching with weighted confidence scores
- Email, phone, whitespace, number, and alphanumeric normalization
- Suggested master based on record completeness
- Native Odoo merge engine for contacts
- Generic relation reassignment for other models
- Reversible archive workflow or protected permanent deletion
- Multi-company security, scheduled scans, and permanent merge audit

## Setup

Give reviewers **Duplicate Data Cleaner / Reviewer** access. Give trusted administrators **Manager** access to create rules and merge records. Open **Data Cleaner → Detection Rules**, configure the rule, and select **Scan Now**.

Always test custom-model merge rules on a staging database before using permanent deletion.
