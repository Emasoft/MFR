#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial creation of orchestrator submodule
# - Added exports for all orchestrator submodules
#

"""
Orchestrator submodule for Mass Find Replace.

This module breaks down the transaction orchestration logic into smaller, focused components.
"""

from .collision_detector import check_rename_collision
from .interactive_handler import (
    prompt_user_for_transaction,
    print_transaction_result,
    print_execution_summary,
    UserChoice,
)
from .retry_handler import (
    identify_retryable_transactions,
    calculate_retry_wait_time,
    handle_retry_wait,
)
from .stats_manager import (
    initialize_stats,
    update_stats_for_status,
    calculate_final_stats,
)
from .transaction_processor import (
    process_rename_transaction,
    should_skip_transaction,
    prepare_content_transaction,
)

__all__ = [
    # Collision detection
    "check_rename_collision",
    # Interactive handling
    "prompt_user_for_transaction",
    "print_transaction_result",
    "print_execution_summary",
    "UserChoice",
    # Retry handling
    "identify_retryable_transactions",
    "calculate_retry_wait_time",
    "handle_retry_wait",
    # Stats management
    "initialize_stats",
    "update_stats_for_status",
    "calculate_final_stats",
    # Transaction processing
    "process_rename_transaction",
    "should_skip_transaction",
    "prepare_content_transaction",
]
