# Executive Summary

## Business Problem
Migrate an on-premises Java monolith and its SQL Server database to the cloud using a pure lift-and-shift approach. SOC 2 requirements are already in scope, the workload includes both Windows and Linux VMs, and the acceptable cutover downtime is 24 hours.

## Confirmed Understanding
- The current environment is on-premises.
- The application is a Java monolith.
- The database is SQL Server.
- The migration approach is lift-and-shift with no application modernization in this phase.
- The environment includes both Windows and Linux VMs.
- CommVault is used for backup and DR today.
- SOC 2 requirements apply, and there are no additional compliance requirements stated.
- The user has existing Windows Server or SQL Server licensing agreements.
- There is no stated budget target or cost-reduction goal.

## Assumptions & Defaults Used
- **Target cloud platform:** Azure was recommended by specialists, but the user has not confirmed a cloud preference. This reduces confidence in provider-specific tooling and licensing assumptions.
- **Operational tooling:** Terraform and Azure DevOps were recommended as a low-risk operational path, but enterprise tooling standards were not confirmed. This may not match the organization’s SDLC conventions.
- **Database target strategy:** SQL Server on IaaS was recommended for migration simplicity. This avoids near-term replatforming benefits and may preserve higher steady-state operating cost.
- **Security posture:** SOC 2-aligned controls were recommended with cloud-native encryption, segmentation, and auditability. Exact control implementation will depend on evidence and policy requirements.
- **FinOps posture:** Hybrid Benefit / BYOL and later reserved commitments were recommended. Savings depend on the exact license terms, sizing, and final cloud platform.

## Top-Line Recommendation
Proceed with a low-change cloud rehost, ideally on Azure if the organization has no conflicting cloud standard. Keep the Java monolith intact, run SQL Server on IaaS initially, and use cloud-native security controls to maintain SOC 2 readiness. Treat the migration as phase one of a broader journey, not the final architecture, and add a post-stabilization checkpoint to reassess the app and database for modernization opportunities.

## What to Validate Next
- Confirm the preferred cloud platform or any enterprise cloud standard.
- Validate the licensing details for Windows Server and SQL Server.
- Define the SOC 2 control evidence plan, especially logging, access reviews, and retention.
- Confirm backup restore and DR testing expectations in the target cloud.
- Confirm whether the organization wants Terraform and Azure DevOps as standards.
- Estimate steady-state TCO versus the current on-prem environment.
