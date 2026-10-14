"""
Builds the Postman collection from a compact definition.

Run from backend/:   python scripts/generate_postman.py
Then in Postman:     Import -> postman/ticket_system.postman_collection.json
"""
import json
from pathlib import Path

OUT_FILE = (
    Path(__file__).resolve().parent.parent / "postman" / "ticket_system.postman_collection.json"
)
V1 = "api/v1"

Query = dict[str, tuple[str, bool]]  # parameter name -> (example value, enabled by default)


def check(status: int) -> list[str]:
    return [
        f'pm.test("Status is {status}", function () {{ pm.response.to.have.status({status}); }});'
    ]


def save(variable: str, expression: str) -> list[str]:
    return [f'pm.collectionVariables.set("{variable}", {expression});']


def save_first_id(variable: str, list_expression: str) -> list[str]:
    return [
        f"const items = {list_expression};",
        f'if (items.length) {{ pm.collectionVariables.set("{variable}", items[0].id); }}',
    ]


def req(
    name: str,
    method: str,
    path: str,
    *,
    body: dict | None = None,
    query: Query | None = None,
    auth: bool = True,
    expect: int = 200,
    tests: list[str] | None = None,
    description: str = "",
    file_upload: bool = False,
) -> dict:
    enabled = [f"{k}={v}" for k, (v, on) in (query or {}).items() if on]
    url: dict = {
        "raw": "{{base_url}}/" + path + ("?" + "&".join(enabled) if enabled else ""),
        "host": ["{{base_url}}"],
        "path": path.split("/"),
    }
    if query:
        url["query"] = [{"key": k, "value": v, "disabled": not on} for k, (v, on) in query.items()]

    request: dict = {"method": method, "header": [], "url": url, "description": description}
    if body is not None:
        request["header"].append({"key": "Content-Type", "value": "application/json"})
        request["body"] = {
            "mode": "raw",
            "raw": json.dumps(body, indent=2),
            "options": {"raw": {"language": "json"}},
        }
    if file_upload:
        request["body"] = {"mode": "formdata", "formdata": [{"key": "file", "type": "file", "src": []}]}
    if not auth:
        request["auth"] = {"type": "noauth"}

    return {
        "name": name,
        "request": request,
        "event": [
            {
                "listen": "test",
                "script": {"type": "text/javascript", "exec": check(expect) + (tests or [])},
            }
        ],
    }


def login(role: str, email: str, password: str) -> dict:
    return req(
        f"Login - {role}",
        "POST",
        f"{V1}/auth/login",
        body={"email": email, "password": password},
        auth=False,
        description=f"Logs in as the seeded {role.lower()} and stores the tokens in collection variables.",
        tests=save("access_token", "pm.response.json().access_token")
        + save("refresh_token", "pm.response.json().refresh_token"),
    )


FOLDERS: dict[str, list[dict]] = {
    "Health": [
        req("Health check", "GET", "health", auth=False),
    ],
    "Auth": [
        req(
            "Register (customer)",
            "POST",
            f"{V1}/auth/register",
            body={"name": "Jane Customer", "email": "jane@example.com", "password": "Password123!"},
            auth=False,
            expect=201,
            description="Public sign-up. The role is always 'customer'.",
        ),
        login("Admin", "admin@example.com", "Admin@12345"),
        login("Agent", "agent1@example.com", "Agent@12345"),
        login("Customer", "customer1@example.com", "Customer@12345"),
        req(
            "Refresh token",
            "POST",
            f"{V1}/auth/refresh",
            body={"refresh_token": "{{refresh_token}}"},
            auth=False,
            description="Each refresh token works once; a new pair is returned.",
            tests=save("access_token", "pm.response.json().access_token")
            + save("refresh_token", "pm.response.json().refresh_token"),
        ),
        req(
            "Logout",
            "POST",
            f"{V1}/auth/logout",
            body={"refresh_token": "{{refresh_token}}"},
            description="Revokes the given refresh token.",
        ),
        req(
            "Current user",
            "GET",
            f"{V1}/auth/me",
            tests=save("user_id", "pm.response.json().id"),
        ),
        req(
            "Change password",
            "POST",
            f"{V1}/auth/change-password",
            body={"current_password": "OldPassword123!", "new_password": "NewPassword456!"},
            description="Signs the user out everywhere. Use your own values, this changes the password.",
        ),
    ],
    "Users (admin)": [
        req(
            "Create user",
            "POST",
            f"{V1}/users",
            body={
                "name": "New Agent",
                "email": "new.agent@example.com",
                "password": "Password123!",
                "role": "agent",
            },
            expect=201,
            tests=save("new_user_id", "pm.response.json().id"),
        ),
        req(
            "List users",
            "GET",
            f"{V1}/users",
            query={"page": ("1", True), "page_size": ("20", True), "role": ("agent", True)},
            description="Filtering by role=agent also stores the first agent's id in {{agent_id}}.",
            tests=save_first_id("agent_id", "pm.response.json().items"),
        ),
        req("Get user", "GET", f"{V1}/users/{{{{new_user_id}}}}"),
        req(
            "Update user",
            "PATCH",
            f"{V1}/users/{{{{new_user_id}}}}",
            body={"name": "Renamed Agent"},
        ),
        req("Activate user", "PATCH", f"{V1}/users/{{{{new_user_id}}}}/activate"),
        req("Deactivate user", "PATCH", f"{V1}/users/{{{{new_user_id}}}}/deactivate"),
        req(
            "Change role",
            "PATCH",
            f"{V1}/users/{{{{new_user_id}}}}/role",
            body={"role": "customer"},
        ),
    ],
    "Categories": [
        req(
            "Create category (admin)",
            "POST",
            f"{V1}/categories",
            body={"name": "Hardware", "description": "Laptops, printers and peripherals"},
            expect=201,
            tests=save("category_id", "pm.response.json().id"),
        ),
        req(
            "List categories",
            "GET",
            f"{V1}/categories",
            query={"active_only": ("true", False)},
            tests=save_first_id("category_id", "pm.response.json()"),
        ),
        req(
            "Update category (admin)",
            "PATCH",
            f"{V1}/categories/{{{{category_id}}}}",
            body={"description": "Updated description"},
        ),
        req("Activate category (admin)", "PATCH", f"{V1}/categories/{{{{category_id}}}}/activate"),
        req("Deactivate category (admin)", "PATCH", f"{V1}/categories/{{{{category_id}}}}/deactivate"),
    ],
    "Tickets": [
        req(
            "Create ticket",
            "POST",
            f"{V1}/tickets",
            body={
                "title": "Cannot log in to the portal",
                "description": "I get an error every time I try to log in.",
                "category_id": "{{category_id}}",
                "priority_name": "high",
            },
            expect=201,
            description="priority_name: low | medium | high | critical. Due date is set from the priority's SLA.",
            tests=save("ticket_id", "pm.response.json().id"),
        ),
        req(
            "List tickets",
            "GET",
            f"{V1}/tickets",
            query={
                "page": ("1", True),
                "page_size": ("20", True),
                "search": ("login", False),
                "status": ("open", False),
                "priority": ("high", False),
                "category_id": ("{{category_id}}", False),
                "assigned_agent": ("{{agent_id}}", False),
                "customer": ("{{user_id}}", False),
                "date_from": ("2026-01-01T00:00:00Z", False),
                "date_to": ("2026-12-31T23:59:59Z", False),
                "sort_by": ("created_at", True),
                "sort_order": ("desc", True),
            },
            description="Tick the checkboxes to enable filters. Results are scoped by role.",
            tests=save_first_id("ticket_id", "pm.response.json().items"),
        ),
        req(
            "Export tickets (CSV)",
            "GET",
            f"{V1}/tickets/export",
            query={"status": ("open", False)},
            description="Accepts the same filters as the list. Downloads a .csv.",
        ),
        req("Get ticket", "GET", f"{V1}/tickets/{{{{ticket_id}}}}"),
        req(
            "Update ticket",
            "PATCH",
            f"{V1}/tickets/{{{{ticket_id}}}}",
            body={"title": "Updated ticket title", "priority_name": "critical"},
            description="Changing the priority recalculates the due date.",
        ),
        req(
            "Update status (agent/admin)",
            "PATCH",
            f"{V1}/tickets/{{{{ticket_id}}}}/status",
            body={"status": "in_progress"},
            description="open -> in_progress -> resolved -> closed. Resolved can be reopened to in_progress.",
        ),
        req(
            "Assign ticket (agent/admin)",
            "PATCH",
            f"{V1}/tickets/{{{{ticket_id}}}}/assign",
            body={"agent_id": "{{agent_id}}"},
        ),
        req("Delete ticket (admin)", "DELETE", f"{V1}/tickets/{{{{ticket_id}}}}", expect=204),
    ],
    "Comments": [
        req(
            "Add comment",
            "POST",
            f"{V1}/tickets/{{{{ticket_id}}}}/comments",
            body={"message": "Any update on this?"},
            expect=201,
            tests=save("comment_id", "pm.response.json().id"),
        ),
        req("List comments", "GET", f"{V1}/tickets/{{{{ticket_id}}}}/comments"),
        req(
            "Update own comment",
            "PATCH",
            f"{V1}/comments/{{{{comment_id}}}}",
            body={"message": "Edited comment"},
        ),
        req("Delete own comment", "DELETE", f"{V1}/comments/{{{{comment_id}}}}", expect=204),
    ],
    "Attachments": [
        req(
            "Upload attachment",
            "POST",
            f"{V1}/tickets/{{{{ticket_id}}}}/attachments",
            file_upload=True,
            expect=201,
            description="Choose a PNG/JPEG/GIF/PDF/TXT/DOCX/ZIP up to 10 MB. The type is detected from the file content.",
            tests=save("attachment_id", "pm.response.json().id"),
        ),
        req("List attachments", "GET", f"{V1}/tickets/{{{{ticket_id}}}}/attachments"),
        req("Download attachment", "GET", f"{V1}/attachments/{{{{attachment_id}}}}/download"),
        req("Delete attachment", "DELETE", f"{V1}/attachments/{{{{attachment_id}}}}", expect=204),
    ],
    "Notifications": [
        req(
            "List notifications",
            "GET",
            f"{V1}/notifications",
            query={"unread_only": ("true", False)},
            tests=save_first_id("notification_id", "pm.response.json()"),
        ),
        req("Mark as read", "PATCH", f"{V1}/notifications/{{{{notification_id}}}}/read"),
        req("Mark all as read", "PATCH", f"{V1}/notifications/read-all"),
    ],
    "Dashboard": [
        req("Ticket stats (scoped by role)", "GET", f"{V1}/dashboard/stats"),
        req("Admin stats (admin)", "GET", f"{V1}/dashboard/admin"),
        req("Agent stats (agent)", "GET", f"{V1}/dashboard/agent"),
    ],
    "Audit Logs (admin)": [
        req(
            "List audit logs",
            "GET",
            f"{V1}/audit-logs",
            query={
                "page": ("1", True),
                "page_size": ("20", True),
                "action": ("login", False),
                "user_id": ("{{user_id}}", False),
                "entity": ("ticket", False),
                "entity_id": ("{{ticket_id}}", False),
                "date_from": ("2026-01-01T00:00:00Z", False),
                "date_to": ("2026-12-31T23:59:59Z", False),
            },
            description="Read-only. There is no endpoint to modify audit records.",
        ),
    ],
}

COLLECTION = {
    "info": {
        "name": "Support Ticket Management System",
        "description": (
            "1. Run the seed script (python scripts/seed_demo.py).\n"
            "2. Run one of the 'Login' requests in the Auth folder; it stores the token.\n"
            "3. Call any endpoint. To test another role, log in as that role first.\n\n"
            "Live notifications use a WebSocket: ws://localhost:8000/ws/notifications?token=<access_token>"
        ),
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{access_token}}", "type": "string"}]},
    "variable": [
        {"key": key, "value": value}
        for key, value in {
            "base_url": "http://localhost:8000",
            "access_token": "",
            "refresh_token": "",
            "user_id": "",
            "new_user_id": "",
            "agent_id": "",
            "category_id": "",
            "ticket_id": "",
            "comment_id": "",
            "attachment_id": "",
            "notification_id": "",
        }.items()
    ],
    "item": [{"name": name, "item": items} for name, items in FOLDERS.items()],
}

if __name__ == "__main__":
    OUT_FILE.parent.mkdir(exist_ok=True)
    OUT_FILE.write_text(json.dumps(COLLECTION, indent=2), encoding="utf-8")
    total = sum(len(items) for items in FOLDERS.values())
    print(f"Wrote {total} requests to {OUT_FILE}")