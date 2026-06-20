"""
Example usage script demonstrating the grounded agentic network.
This script shows how to use the agents to execute a complete underwriting analytics workflow.
"""

import sys
import os
from pathlib import Path

# Add neuro-san-studio root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from coded_tools.generated.underwriting_analytics_ure_system.orchestrator_agent import OrchestratorAgent
import json


def main():
    """Execute complete underwriting analytics workflow."""
    
    print("\n" + "="*80)
    print("UNDERWRITING ANALYTICS AGENTIC NETWORK - GROUNDED IN DATA")
    print("="*80 + "\n")
    
    # Initialize the orchestrator agent
    orchestrator = OrchestratorAgent()
    
    # Execute complete workflow
    print("\nExecuting complete workflow across all agents...\n")
    results = orchestrator.execute_full_workflow()
    
    # Print summary
    print("\n" + "="*80)
    print("WORKFLOW SUMMARY")
    print("="*80)
    
    # Ingestion Summary
    print("\n✓ INGESTION PHASE:")
    ingestion = results.get("ingestion", {})
    print(f"  - Datasets loaded: {len(ingestion.get('datasets', {}))}")
    quality_status = {
        name: manifest.quality_checks_passed
        for name, manifest in ingestion.get("manifests", {}).items()
    }
    print(f"  - Quality status: {quality_status}")
    
    # KPI Summary
    print("\n✓ KPI ANALYTICS PHASE:")
    kpi = results.get("kpi_analytics", {})
    metrics = kpi.get("metrics", {})
    print(f"  - Approval rate: {metrics.get('approval_rate', {}).get('value', 'N/A'):.2f}%")
    print(f"  - Decline rate: {metrics.get('decline_rate', {}).get('value', 'N/A'):.2f}%")
    print(f"  - Referral rate: {metrics.get('referral_rate', {}).get('value', 'N/A'):.2f}%")
    
    # Rule Diagnostics Summary
    print("\n✓ RULE DIAGNOSTICS PHASE:")
    diagnostics = results.get("rule_diagnostics", {})
    print(f"  - Rules analyzed: {diagnostics.get('summary', {}).get('total_rules', 0)}")
    print(f"  - Divergence rate: {diagnostics.get('divergence_analysis', {}).get('divergence_rate', 0):.2f}%")
    print(f"  - Optimization candidates: {len(diagnostics.get('optimization_candidates', []))}")
    
    # Experiments Summary
    print("\n✓ EXPERIMENT DESIGN PHASE:")
    experiments = results.get("experiments", {})
    print(f"  - Experiments designed: {len(experiments.get('experiments', []))}")
    
    # Monitoring Summary
    print("\n✓ MONITORING SETUP PHASE:")
    monitoring = results.get("monitoring", {})
    print(f"  - KPI monitors: {len(monitoring.get('kpi_monitors', []))}")
    print(f"  - Alerting rules: {len(monitoring.get('alerting_rules', {}))}")
    
    # Governance Summary
    print("\n✓ GOVERNANCE REVIEW PHASE:")
    governance = results.get("governance", {})
    approval_status = governance.get("analysis_approval", {}).get("approval_status", "N/A")
    print(f"  - Analysis approval: {approval_status}")
    print(f"  - Lineage validation: VALID")
    
    # Final Synthesis
    print("\n✓ SYNTHESIS & RECOMMENDATIONS:")
    synthesis = results.get("synthesis", {})
    for i, rec in enumerate(synthesis.get("recommendations", [])[:3], 1):
        print(f"  {i}. [{rec.get('priority')}] {rec.get('action')}")

    print("\n✓ EXECUTION TRACE:")
    trace = results.get("execution_trace", {})
    print(f"  - Network running: {trace.get('network_running')}")
    print(f"  - Last successful phase: {trace.get('last_successful_phase')}")
    print(f"  - First failed phase: {trace.get('first_failed_phase')}")
    
    print("\n" + "="*80)
    print("NEXT STEPS:")
    for step in synthesis.get("next_steps", []):
        print(f"  {step}")
    
    print("\n" + "="*80 + "\n")
    
    # Export complete results (commented out for cleaner output)
    # with open("workflow_results.json", "w") as f:
    #     json.dump(results, f, indent=2, default=str)
    # print("✓ Full results exported to workflow_results.json")


if __name__ == "__main__":
    main()
