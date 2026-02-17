#!/usr/bin/env python3
"""
Docker entrypoint for QuickBooks Online invoice processing.

Usage:
    python entrypoint.py --send-invoices    # Send today's invoices
    python entrypoint.py --create-invoices  # Create monthly invoices from usage
"""

import sys
import logging
import argparse

# Import the main functions from shared modules
from process_and_send_qbo_invoices import send_qbo_invoices
from task_minutes_to_clickup_and_qbo import process_all_clients
from sync_robocorp_processes import sync_robocorp_processes_to_sql


def setup_logging():
    """Configure logging for Docker (stdout/stderr)."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def main():
    """Main entrypoint for the Docker container."""
    setup_logging()
    logger = logging.getLogger(__name__)

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='QuickBooks Online Invoice Processor'
    )
    parser.add_argument(
        '--send-invoices',
        action='store_true',
        help='Send today\'s QuickBooks Online invoices to clients'
    )
    parser.add_argument(
        '--create-invoices',
        action='store_true',
        help='Create monthly invoices from Robocorp automation usage'
    )
    parser.add_argument(
        '--sync-processes',
        action='store_true',
        help='Sync Robocorp process/assistant data to Azure SQL Server'
    )

    args = parser.parse_args()

    # Validate that exactly one action is specified
    actions = [args.send_invoices, args.create_invoices, args.sync_processes]
    if sum(actions) == 0:
        logger.error("Error: You must specify one action: --send-invoices, --create-invoices, or --sync-processes")
        parser.print_help()
        sys.exit(1)

    if sum(actions) > 1:
        logger.error("Error: You can only specify one action at a time")
        parser.print_help()
        sys.exit(1)

    # Execute the requested action
    try:
        if args.send_invoices:
            logger.info("=" * 60)
            logger.info("Starting: Send QuickBooks Online Invoices")
            logger.info("=" * 60)
            success = send_qbo_invoices()

        elif args.create_invoices:
            logger.info("=" * 60)
            logger.info("Starting: Create Monthly Invoices from Usage Data")
            logger.info("=" * 60)
            success = process_all_clients()

        elif args.sync_processes:
            logger.info("=" * 60)
            logger.info("Starting: Sync Robocorp Processes to Azure SQL")
            logger.info("=" * 60)
            success = sync_robocorp_processes_to_sql()

        # Exit with appropriate status code
        if success:
            logger.info("=" * 60)
            logger.info("COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)
            sys.exit(0)
        else:
            logger.error("=" * 60)
            logger.error("FAILED - Check logs for details")
            logger.error("=" * 60)
            sys.exit(1)

    except Exception as e:
        logger.exception(f"Unhandled exception occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
