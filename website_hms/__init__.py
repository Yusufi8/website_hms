# -*- coding: utf-8 -*-
from . import models
from . import controllers


def _ensure_employee_flag_columns(env):
    """
    Hotfix for DB schema drift: guarantee is_doctor / is_nurse columns exist.
    Uses IF NOT EXISTS — completely safe to run multiple times.
    """
    env.cr.execute(
        "ALTER TABLE hr_employee ADD COLUMN IF NOT EXISTS is_doctor boolean DEFAULT false"
    )
    env.cr.execute(
        "ALTER TABLE hr_employee ADD COLUMN IF NOT EXISTS is_nurse boolean DEFAULT false"
    )


def _cleanup_conflicting_hospital_pages(env):
    """
    Controllers lose route priority if a website page exists at /hospital.
    Keep the old page content by moving it to a legacy URL instead of deleting it.
    """
    Page = env["website.page"].sudo()
    pages = Page.search([("url", "=", "/hospital")])
    for page in pages:
        view = page.view_id
        if view and view.key and view.key.startswith("website_hms."):
            continue
        page.write({
            "url": "/hospital-legacy-%s" % page.id,
            "is_published": False,
        })


def _setup_menu(env):
    """
    Attach the single Hospital menu entry to the active website navigation root.
    """
    Website = env["website"]
    Menu = env["website.menu"]

    website = Website.search([("name", "ilike", "YK")], limit=1)
    if not website:
        website = Website.search([], limit=1)
    if not website:
        return

    root = Menu.search([
        ("website_id", "=", website.id),
        ("parent_id", "=", False),
    ], limit=1)
    if not root:
        return

    menu = env.ref("website_hms.wm_hospital_root", raise_if_not_found=False)
    if not menu:
        return

    menu.write({
        "parent_id": root.id,
        "website_id": website.id,
        "sequence": 60,
    })


def post_init_hook(env):
    _ensure_employee_flag_columns(env)
    _cleanup_conflicting_hospital_pages(env)
    _setup_menu(env)
