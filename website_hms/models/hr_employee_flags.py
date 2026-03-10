# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrEmployeeFlags(models.Model):
    _inherit = "hr.employee"

    is_doctor = fields.Boolean(
        string='Is Doctor',
        default=False,
        help='Mark this employee as a licensed medical doctor visible in the appointment booking dropdown.',
    )
    is_nurse = fields.Boolean(
        string='Is Nurse',
        default=False,
        help='Mark this employee as a registered nurse.',
    )


class HospitalPatientPortal(models.Model):
    _inherit = "hospital.patient"

    owner_user_id = fields.Many2one(
        "res.users",
        string="Portal Owner",
        index=True,
        copy=False,
        tracking=True,
        help="Website user who owns and manages this patient record.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if not vals.get("reference") or vals.get("reference") == "New":
                vals["reference"] = sequence.next_by_code("hospital.patient") or "New"
        return super().create(vals_list)


class HospitalAppointmentPortal(models.Model):
    _inherit = "hospital.appointment"

    owner_user_id = fields.Many2one(
        "res.users",
        string="Portal Owner",
        index=True,
        copy=False,
        tracking=True,
        help="Website user who owns and manages this appointment.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if not vals.get("reference") or vals.get("reference") == "New":
                vals["reference"] = sequence.next_by_code("hospital.appointment") or "New"
            if not vals.get("owner_user_id") and vals.get("patient_id"):
                patient = self.env["hospital.patient"].sudo().browse(vals["patient_id"])
                if patient.exists() and patient.owner_user_id:
                    vals["owner_user_id"] = patient.owner_user_id.id
        return super().create(vals_list)


class WebsiteHMSBootstrap(models.Model):
    _inherit = "website"

    @api.model
    def hms_bootstrap_portal(self):
        menu = self.env.ref("website_hms.wm_hospital_root", raise_if_not_found=False)
        Menu = self.env["website.menu"].sudo()
        Page = self.env["website.page"].sudo()

        pages = Page.search([("url", "=", "/hospital")])
        for page in pages:
            view = page.view_id
            if view and view.key and view.key.startswith("website_hms."):
                continue
            page.write({
                "url": "/hospital-legacy-%s" % page.id,
                "is_published": False,
            })

        if not menu:
            return True

        website = self.search([("name", "ilike", "YK")], limit=1) or self.search([], limit=1)
        if not website:
            return True

        root = Menu.search([
            ("website_id", "=", website.id),
            ("parent_id", "=", False),
        ], limit=1)
        if not root:
            return True

        menu.sudo().write({
            "parent_id": root.id,
            "website_id": website.id,
            "sequence": 60,
        })
        return True
