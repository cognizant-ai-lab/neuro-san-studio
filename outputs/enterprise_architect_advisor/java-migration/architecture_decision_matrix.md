# Architecture Decision Matrix

| Decision Area | Recommended Option | Score /100 | Why Recommended | Alternatives Considered |
|---|---|---:|---|---|
| Cloud Platform | Azure | 86 | Strong fit for on-prem VM migration, Windows/Linux support, SQL Server alignment, and Microsoft licensing benefits. | AWS, GCP, hybrid, multi-cloud |
| Migration Strategy | Rehost / lift-and-shift | 92 | Best aligned to the explicit requirement for minimal change and a 24-hour cutover window. | Refactor, replatform, rebuild |
| Application Hosting Model | VMs (IaaS) | 90 | Preserves current runtime and reduces migration risk for a Java monolith. | Containers, PaaS, serverless |
| Application Architecture | Keep monolith | 88 | Avoids unnecessary change during the migration phase. | Modular monolith, microservices, event-driven |
| Database Target Strategy | SQL Server on IaaS VM | 84 | Simplest near-term path with the least migration friction. | Azure SQL Managed Instance, Azure SQL Database, replatform to another database engine |
| Security Baseline | SOC 2-aligned cloud controls | 87 | Supports auditability, encryption, segmentation, and access governance. | Minimal baseline security, delayed hardening |
| Operations Tooling | Terraform + Azure DevOps + native monitoring | 79 | Good enterprise-operable default for a VM migration, though platform preference was not confirmed. | Other IaC/CI-CD stacks, fully bespoke tooling |
| FinOps / Commercial Model | Hybrid Benefit / BYOL + later reservations | 83 | Uses existing Microsoft licensing to reduce cost, with commitment timing deferred until steady state. | Pure PAYG, immediate reservations, unmanaged spend |

## Notes
- This matrix reflects a deliberately conservative migration posture.
- The strongest recommendation is to treat the cloud move as a rehost first, modernization later decision.
- Provider-specific choices should be revisited if the organization has a mandated cloud standard.
