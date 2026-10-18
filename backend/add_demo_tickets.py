from app.ingest import ingest_ticket
from app.database import SessionLocal
from app.models import Ticket

tickets = [
    {
        "ticket_id": "T-DEMO-001",
        "title": "S/4HANA sales orders load slowly",
        "description": "S/4HANA sales order transactions take too long to load during peak business hours.",
        "system": "S/4HANA",
        "category": "performance",
        "priority": "high",
        "support_level": "L3",
        "resolution": "Review expensive SQL statements, check database memory utilization, inspect long-running work processes, and analyze workload statistics.",
        "resolver": "performance.team",
        "resolution_time_hours": 6.0,
    },
    {
        "ticket_id": "T-DEMO-002",
        "title": "ABAP user receives authorization error",
        "description": "An ABAP user receives an authorization error when executing a custom report. SU53 shows a missing object. SAP Note 1234567 was referenced in a previous resolution.",
        "system": "ABAP",
        "category": "authorization",
        "priority": "critical",
        "support_level": "L2",
        "resolution": "Use SU53 to identify the missing authorization object, validate the role assignment, and retest the custom report.",
        "resolver": "security.team",
        "resolution_time_hours": 3.0,
    },
    {
        "ticket_id": "T-DEMO-003",
        "title": "HANA backup job failed",
        "description": "The scheduled HANA database backup failed and the latest backup is not available.",
        "system": "HANA",
        "category": "backup",
        "priority": "high",
        "support_level": "L2",
        "resolution": "Review backup logs, verify the backup destination, check available disk space, and rerun the database backup after correcting the failure.",
        "resolver": "hana.admin",
        "resolution_time_hours": 4.5,
    },
    {
        "ticket_id": "T-DEMO-004",
        "title": "NetWeaver upgrade stopped during import",
        "description": "The NetWeaver upgrade stopped during the software import phase with an activation error.",
        "system": "NetWeaver",
        "category": "upgrade",
        "priority": "high",
        "support_level": "L3",
        "resolution": "Review the upgrade logs, resolve inactive objects, verify the transport directory, and repeat the failed upgrade phase.",
        "resolver": "upgrade.team",
        "resolution_time_hours": 12.0,
    },
    {
        "ticket_id": "T-DEMO-005",
        "title": "Fiori launchpad authentication failed",
        "description": "Users cannot authenticate to the Fiori launchpad after an identity provider configuration change.",
        "system": "Fiori",
        "category": "authentication",
        "priority": "high",
        "support_level": "L2",
        "resolution": "Verify the SAML identity provider configuration, check certificate validity, validate redirect URLs, and retest the Fiori launchpad login.",
        "resolver": "fiori.team",
        "resolution_time_hours": 5.0,
    },
    {
        "ticket_id": "T-DEMO-006",
        "title": "CPI integration flow fails authorization",
        "description": "A CPI integration flow fails because the sender system is not authorized to call the receiver endpoint.",
        "system": "CPI",
        "category": "authorization",
        "priority": "critical",
        "support_level": "L2",
        "resolution": "Verify OAuth or client certificate credentials, check the receiver security policy, update the required permissions, and retest the integration flow.",
        "resolver": "integration.team",
        "resolution_time_hours": 3.5,
    },
    {
        "ticket_id": "T-DEMO-007",
        "title": "SAP installation failed during database setup",
        "description": "The SAP installation failed while creating the database schema on the application server.",
        "system": "SAP",
        "category": "installation",
        "priority": "high",
        "support_level": "L3",
        "resolution": "Review the installation logs, verify database connectivity and privileges, correct the database configuration, and restart the failed installation phase.",
        "resolver": "basis.team",
        "resolution_time_hours": 8.0,
    },
    {
        "ticket_id": "T-DEMO-008",
        "title": "S/4HANA user cannot access finance application",
        "description": "A finance user can log in to S/4HANA but cannot open the required finance application.",
        "system": "S/4HANA",
        "category": "authorization",
        "priority": "medium",
        "support_level": "L2",
        "resolution": "Check the user's assigned business role, review authorization traces, add the missing catalog or role, and retest application access.",
        "resolver": "authorization.team",
        "resolution_time_hours": 4.0,
    },
    {
        "ticket_id": "T-DEMO-009",
        "title": "HANA high memory consumption",
        "description": "The HANA database reports high memory consumption and application queries are becoming slow. ST03N and ST22 dumps appear during peak load. Related SAP Note 2345678.",
        "system": "HANA",
        "category": "performance",
        "priority": "critical",
        "support_level": "L3",
        "resolution": "Review expensive statements, identify memory-intensive tables, check workload history, and optimize or terminate unnecessary long-running queries.",
        "resolver": "hana.performance",
        "resolution_time_hours": 7.0,
    },
    {
        "ticket_id": "T-DEMO-010",
        "title": "ABAP transport import failed",
        "description": "An ABAP transport request failed during import into the quality assurance system.",
        "system": "ABAP",
        "category": "transport",
        "priority": "medium",
        "support_level": "L2",
        "resolution": "Review the transport logs, check object dependencies, verify the import sequence, and re-import the request after resolving the reported error.",
        "resolver": "transport.team",
        "resolution_time_hours": 3.0,
    },
    {
        "ticket_id": "T-DEMO-011",
        "title": "SAP user locked after password reset",
        "description": "User cannot login after password reset. Account shows locked in SU01.",
        "system": "SAP",
        "category": "authentication",
        "priority": "medium",
        "support_level": "L1",
        "resolution": "Unlock the user in SU01, confirm the temporary password, and ask the user to log in and change the password.",
        "resolver": "service.desk",
        "resolution_time_hours": 0.5,
    },
]

with SessionLocal() as db:
    for data in tickets:
        existing = db.query(Ticket).filter(
            Ticket.ticket_id == data["ticket_id"]
        ).first()

        if existing:
            print(f"SKIP {data['ticket_id']} - already exists")
            continue

        ticket = Ticket(
            ticket_id=data["ticket_id"],
            title=data["title"],
            description=data["description"],
            system=data["system"],
            category=data["category"],
            priority=data["priority"],
            support_level=data.get("support_level"),
            support_level_reason=data.get("support_level_reason"),
            status="resolved",
            resolution=data["resolution"],
            resolver=data["resolver"],
            resolution_time_hours=data["resolution_time_hours"],
        )

        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        result = ingest_ticket(ticket, db)
        print(f"OK {result['ticket_id']} - {result['chunk_count']} chunk")

print("Demo ticket ingestion complete.")
