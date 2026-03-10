# -*- coding: utf-8 -*-
from urllib.parse import urlencode
import logging

from odoo import fields, http
from odoo.exceptions import ValidationError, UserError
from odoo.http import request
from odoo.osv import expression

_logger = logging.getLogger(__name__)

PATIENT_LIMIT = 20
APPOINTMENT_LIMIT = 20
GUARDIAN_OPTIONS = {"Father", "Mother", "Brother", "Sister", "Friend"}
GENDER_OPTIONS = {"male", "female"}
PRIORITY_OPTIONS = {"0", "1", "2", "3"}


def _clean_text(value):
    return (value or "").strip()


def _is_authenticated():
    try:
        public_user = request.env.ref("base.public_user")
        return request.env.user != public_user
    except Exception:
        return False


def _is_hms_admin():
    try:
        user = request.env.user
        return (
            user._is_admin()
            or user.has_group("hospital_yk.group_hms_admin")
            or user.has_group("base.group_system")
        )
    except Exception:
        return False


def _redirect_with_flash(path, message, level="ok"):
    query = urlencode({"flash": message, "ft": level})
    separator = "&" if "?" in path else "?"
    return request.redirect("%s%s%s" % (path, separator, query))


def _owner_domain(user_id=None):
    return [("owner_user_id", "=", user_id or request.env.user.id)]


def _patient_model():
    return request.env["hospital.patient"].sudo()


def _appointment_model():
    return request.env["hospital.appointment"].sudo()


def _doctor_model():
    return request.env["hr.employee"].sudo()


def _get_doctors():
    try:
        return _doctor_model().search([("is_doctor", "=", True)], order="name asc", limit=50)
    except Exception as exc:
        _logger.warning("website_hms: failed to fetch doctors: %s", exc)
        return _doctor_model().browse([])


def _make_datetime_input(value):
    if not value:
        return ""
    try:
        localized = fields.Datetime.context_timestamp(request.env.user, value)
        return localized.strftime("%Y-%m-%dT%H:%M")
    except Exception:
        return ""


def _patient_form_defaults(record=None):
    if not record:
        return {
            "name": "",
            "gender": "",
            "date_of_birth": "",
            "mobile": "",
            "email": "",
            "address": "",
            "guardian": "",
            "guardian_name": "",
            "guardian_mobile": "",
            "medical_history": "",
            "notes": "",
        }
    return {
        "name": record.name or "",
        "gender": record.gender or "",
        "date_of_birth": record.date_of_birth.isoformat() if record.date_of_birth else "",
        "mobile": record.mobile or "",
        "email": record.email or "",
        "address": record.address or "",
        "guardian": record.guardian or "",
        "guardian_name": record.guardian_name or "",
        "guardian_mobile": record.guardian_mobile or "",
        "medical_history": record.medical_history or "",
        "notes": record.notes or "",
    }


def _appointment_form_defaults(record=None):
    if not record:
        return {
            "patient_id": "",
            "appointment_date": "",
            "doctor_id": "",
            "priority": "2",
            "notes": "",
        }
    return {
        "patient_id": str(record.patient_id.id or ""),
        "appointment_date": _make_datetime_input(record.appointment_date),
        "doctor_id": str(record.doctor_id.id or ""),
        "priority": record.priority or "2",
        "notes": record.notes or "",
    }


def _patient_form_context(record=None, form_data=None, errors=None, flash="", flash_type="ok"):
    is_edit = bool(record)
    return {
        "flash": flash,
        "flash_type": flash_type,
        "errors": errors or {},
        "fd": form_data or _patient_form_defaults(record),
        "patient_record": record,
        "form_mode": "edit" if is_edit else "create",
        "page_title": "Edit Patient" if is_edit else "Register Patient",
        "page_subtitle": (
            "Update patient details, contacts and health notes."
            if is_edit else
            "Create a secure patient profile for future appointments and follow-ups."
        ),
        "submit_url": (
            "/hospital/patient/%s/update" % record.id
            if is_edit else "/hospital/create-patient/submit"
        ),
        "primary_action_label": "Save Changes" if is_edit else "Register Patient",
        "secondary_action_label": "Back to My Patients" if is_edit else "Go to Dashboard",
        "secondary_action_url": "/hospital/my-patients" if is_edit else "/hospital/dashboard",
    }


def _appointment_form_context(record=None, form_data=None, errors=None, flash="", flash_type="ok"):
    is_edit = bool(record)
    domain = [] if _is_hms_admin() else _owner_domain()
    patients = _patient_model().search(domain, order="name asc, id desc", limit=100)
    return {
        "flash": flash,
        "flash_type": flash_type,
        "errors": errors or {},
        "fd": form_data or _appointment_form_defaults(record),
        "appointment_record": record,
        "patients": patients,
        "doctors": _get_doctors(),
        "form_mode": "edit" if is_edit else "create",
        "page_title": "Edit Appointment" if is_edit else "Book Appointment",
        "page_subtitle": (
            "Update timing, doctor preference and visit notes for this booking."
            if is_edit else
            "Schedule a consultation with the right specialist at the right time."
        ),
        "submit_url": (
            "/hospital/appointment/%s/update" % record.id
            if is_edit else "/hospital/book-appointment/submit"
        ),
        "primary_action_label": "Update Appointment" if is_edit else "Confirm Appointment",
        "secondary_action_label": "Back to My Appointments" if is_edit else "Back to Dashboard",
        "secondary_action_url": "/hospital/my-appointments" if is_edit else "/hospital/dashboard",
    }


def _find_patient(patient_id):
    patient = _patient_model().browse(patient_id)
    if not patient.exists():
        return False
    if _is_hms_admin():
        return patient
    return patient if patient.owner_user_id.id == request.env.user.id else False


def _find_appointment(appointment_id):
    appointment = _appointment_model().browse(appointment_id)
    if not appointment.exists():
        return False
    if _is_hms_admin():
        return appointment
    return appointment if appointment.owner_user_id.id == request.env.user.id else False


def _parse_patient_values(post, record=None):
    errors = {}
    name = _clean_text(post.get("name"))
    gender = _clean_text(post.get("gender"))
    mobile = _clean_text(post.get("mobile"))
    guardian = _clean_text(post.get("guardian"))
    date_of_birth = _clean_text(post.get("date_of_birth"))

    if not name:
        errors["name"] = "Full name is required."
    if gender not in GENDER_OPTIONS:
        errors["gender"] = "Select a valid gender."
    if not mobile:
        errors["mobile"] = "Mobile number is required."
    if guardian and guardian not in GUARDIAN_OPTIONS:
        errors["guardian"] = "Select a valid guardian relation."

    values = {
        "name": name,
        "gender": gender or False,
        "mobile": mobile,
        "email": _clean_text(post.get("email")) or False,
        "date_of_birth": date_of_birth or False,
        "guardian": guardian or False,
        "guardian_name": _clean_text(post.get("guardian_name")) or False,
        "guardian_mobile": _clean_text(post.get("guardian_mobile")) or False,
        "address": _clean_text(post.get("address")) or False,
        "medical_history": _clean_text(post.get("medical_history")) or False,
        "notes": _clean_text(post.get("notes")) or False,
    }

    if record and record.owner_user_id and _is_hms_admin():
        values["owner_user_id"] = record.owner_user_id.id
    else:
        values["owner_user_id"] = request.env.user.id

    return values, errors


def _parse_appointment_values(post, record=None):
    errors = {}
    patient_id = _clean_text(post.get("patient_id"))
    appointment_date = _clean_text(post.get("appointment_date"))
    doctor_id = _clean_text(post.get("doctor_id"))
    priority = _clean_text(post.get("priority")) or "2"

    patient = False
    if not patient_id:
        errors["patient_id"] = "Select a patient."
    else:
        try:
            patient = _find_patient(int(patient_id))
        except Exception:
            patient = False
        if not patient:
            errors["patient_id"] = "You can only use patients from your own account."

    parsed_date = False
    if not appointment_date:
        errors["appointment_date"] = "Choose a valid appointment date and time."
    else:
        try:
            parsed_date = fields.Datetime.to_datetime(appointment_date.replace("T", " "))
        except Exception:
            parsed_date = False
        if not parsed_date:
            errors["appointment_date"] = "Choose a valid appointment date and time."

    doctor = False
    if doctor_id:
        try:
            doctor = _doctor_model().search([
                ("id", "=", int(doctor_id)),
                ("is_doctor", "=", True),
            ], limit=1)
        except Exception:
            doctor = False
        if not doctor:
            errors["doctor_id"] = "Choose a valid doctor."

    if priority not in PRIORITY_OPTIONS:
        priority = "2"

    values = {
        "patient_id": patient.id if patient else False,
        "appointment_date": fields.Datetime.to_string(parsed_date) if parsed_date else False,
        "doctor_id": doctor.id if doctor else False,
        "priority": priority,
        "notes": _clean_text(post.get("notes")) or False,
    }

    if record and record.owner_user_id and _is_hms_admin():
        values["owner_user_id"] = record.owner_user_id.id
    elif patient and patient.owner_user_id:
        values["owner_user_id"] = patient.owner_user_id.id
    else:
        values["owner_user_id"] = request.env.user.id

    return values, errors


def _personal_dashboard_context(flash="", flash_type="ok"):
    patient_domain = _owner_domain()
    appointment_domain = _owner_domain()
    now = fields.Datetime.now()
    appointment_model = _appointment_model()

    my_patient_count = _patient_model().search_count(patient_domain)
    my_appointment_count = appointment_model.search_count(appointment_domain)
    upcoming_domain = expression.AND([
        appointment_domain,
        [("appointment_date", ">=", now), ("state", "not in", ["done", "cancelled"])],
    ])

    return {
        "dashboard_scope": "personal",
        "flash": flash,
        "flash_type": flash_type,
        "is_admin": _is_hms_admin(),
        "my_patient_count": my_patient_count,
        "my_appointment_count": my_appointment_count,
        "upcoming_count": appointment_model.search_count(upcoming_domain),
        "confirmed_count": appointment_model.search_count(
            expression.AND([appointment_domain, [("state", "=", "confirmed")]])
        ),
        "recent_patients": _patient_model().search(
            patient_domain, order="write_date desc, id desc", limit=6
        ),
        "recent_appointments": appointment_model.search(
            appointment_domain, order="appointment_date desc, id desc", limit=6
        ),
        "upcoming_appointments": appointment_model.search(
            upcoming_domain, order="appointment_date asc", limit=6
        ),
        "show_empty_state": not my_patient_count and not my_appointment_count,
    }


def _admin_dashboard_context(flash="", flash_type="ok"):
    now = fields.Datetime.now()
    patient_model = _patient_model()
    appointment_model = _appointment_model()
    return {
        "dashboard_scope": "admin",
        "flash": flash,
        "flash_type": flash_type,
        "is_admin": True,
        "total_patients": patient_model.search_count([]),
        "total_appointments": appointment_model.search_count([]),
        "active_portal_patients": patient_model.search_count([("owner_user_id", "!=", False)]),
        "upcoming_count": appointment_model.search_count([
            ("appointment_date", ">=", now),
            ("state", "not in", ["done", "cancelled"]),
        ]),
        "confirmed_count": appointment_model.search_count([("state", "=", "confirmed")]),
        "draft_count": appointment_model.search_count([("state", "=", "draft")]),
        "done_count": appointment_model.search_count([("state", "=", "done")]),
        "recent_patients": patient_model.search([], order="id desc", limit=10),
        "recent_appointments": appointment_model.search([], order="id desc", limit=10),
        "upcoming_appointments": appointment_model.search([
            ("appointment_date", ">=", now),
            ("state", "not in", ["done", "cancelled"]),
        ], order="appointment_date asc", limit=10),
    }


class HMSWebsite(http.Controller):

    @http.route("/hospital", type="http", auth="public", website=True, methods=["GET"])
    def hospital_home(self, **kw):
        return request.render("website_hms.tmpl_home", {
            "flash": kw.get("flash", ""),
            "flash_type": kw.get("ft", "ok"),
            "is_auth": _is_authenticated(),
            "is_admin": _is_hms_admin(),
            "total_patients": _patient_model().search_count([]),
            "total_appointments": _appointment_model().search_count([]),
            "upcoming_count": _appointment_model().search_count([
                ("appointment_date", ">=", fields.Datetime.now()),
                ("state", "not in", ["done", "cancelled"]),
            ]),
        })

    @http.route("/hospital/dashboard", type="http", auth="user", website=True, methods=["GET"])
    def hospital_dashboard(self, **kw):
        return request.render(
            "website_hms.tmpl_dashboard",
            _personal_dashboard_context(kw.get("flash", ""), kw.get("ft", "ok")),
        )

    @http.route("/hospital/dashboard/admin", type="http", auth="user", website=True, methods=["GET"])
    def hospital_dashboard_admin(self, **kw):
        if not _is_hms_admin():
            return _redirect_with_flash(
                "/hospital/dashboard",
                "Global dashboard access is restricted to Hospital Administrators.",
                "err",
            )
        return request.render(
            "website_hms.tmpl_dashboard",
            _admin_dashboard_context(kw.get("flash", ""), kw.get("ft", "ok")),
        )

    @http.route("/hospital/my-patients", type="http", auth="user", website=True, methods=["GET"])
    def my_patients(self, search="", **kw):
        search = _clean_text(search)
        domain = [] if _is_hms_admin() else _owner_domain()
        if search:
            domain = expression.AND([
                domain,
                expression.OR([
                    [("name", "ilike", search)],
                    [("reference", "ilike", search)],
                    [("mobile", "ilike", search)],
                ]),
            ])
        patients = _patient_model().search(domain, order="write_date desc, id desc", limit=PATIENT_LIMIT)
        return request.render("website_hms.tmpl_my_patients", {
            "flash": kw.get("flash", ""),
            "flash_type": kw.get("ft", "ok"),
            "patients": patients,
            "search": search,
            "is_admin": _is_hms_admin(),
            "result_count": _patient_model().search_count(domain),
        })

    @http.route("/hospital/my-appointments", type="http", auth="user", website=True, methods=["GET"])
    def my_appointments(self, search="", **kw):
        search = _clean_text(search)
        domain = [] if _is_hms_admin() else _owner_domain()
        if search:
            domain = expression.AND([
                domain,
                expression.OR([
                    [("reference", "ilike", search)],
                    [("patient_id.name", "ilike", search)],
                    [("doctor_id.name", "ilike", search)],
                ]),
            ])
        appointments = _appointment_model().search(
            domain, order="appointment_date desc, id desc", limit=APPOINTMENT_LIMIT
        )
        return request.render("website_hms.tmpl_my_appointments", {
            "flash": kw.get("flash", ""),
            "flash_type": kw.get("ft", "ok"),
            "appointments": appointments,
            "search": search,
            "is_admin": _is_hms_admin(),
            "result_count": _appointment_model().search_count(domain),
        })

    @http.route("/hospital/create-patient", type="http", auth="user", website=True, methods=["GET"])
    def create_patient_get(self, **kw):
        return request.render(
            "website_hms.tmpl_create_patient",
            _patient_form_context(flash=kw.get("flash", ""), flash_type=kw.get("ft", "ok")),
        )

    @http.route(
        "/hospital/create-patient/submit",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def create_patient_post(self, **post):
        values, errors = _parse_patient_values(post)
        if errors:
            return request.render(
                "website_hms.tmpl_create_patient",
                _patient_form_context(form_data=post, errors=errors),
            )
        try:
            patient = _patient_model().create(values)
            return request.render("website_hms.tmpl_create_patient_success", {
                "patient": patient,
                "is_admin": _is_hms_admin(),
            })
        except (ValidationError, UserError) as exc:
            return request.render(
                "website_hms.tmpl_create_patient",
                _patient_form_context(form_data=post, errors={"general": str(exc)}),
            )
        except Exception as exc:
            _logger.exception("website_hms: create patient failed")
            return request.render(
                "website_hms.tmpl_create_patient",
                _patient_form_context(
                    form_data=post,
                    errors={"general": "We could not save this patient right now. %s" % exc},
                ),
            )

    @http.route("/hospital/patient/<int:patient_id>/edit", type="http", auth="user", website=True, methods=["GET"])
    def edit_patient_get(self, patient_id, **kw):
        patient = _find_patient(patient_id)
        if not patient:
            return _redirect_with_flash(
                "/hospital/my-patients",
                "That patient is unavailable or outside your account.",
                "err",
            )
        return request.render(
            "website_hms.tmpl_create_patient",
            _patient_form_context(
                record=patient,
                flash=kw.get("flash", ""),
                flash_type=kw.get("ft", "ok"),
            ),
        )

    @http.route(
        "/hospital/patient/<int:patient_id>/update",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def edit_patient_post(self, patient_id, **post):
        patient = _find_patient(patient_id)
        if not patient:
            return _redirect_with_flash(
                "/hospital/my-patients",
                "That patient is unavailable or outside your account.",
                "err",
            )
        values, errors = _parse_patient_values(post, record=patient)
        if errors:
            return request.render(
                "website_hms.tmpl_create_patient",
                _patient_form_context(record=patient, form_data=post, errors=errors),
            )
        try:
            patient.write(values)
            return _redirect_with_flash(
                "/hospital/my-patients",
                "Patient details updated successfully.",
                "ok",
            )
        except (ValidationError, UserError) as exc:
            return request.render(
                "website_hms.tmpl_create_patient",
                _patient_form_context(record=patient, form_data=post, errors={"general": str(exc)}),
            )
        except Exception as exc:
            _logger.exception("website_hms: update patient failed")
            return request.render(
                "website_hms.tmpl_create_patient",
                _patient_form_context(
                    record=patient,
                    form_data=post,
                    errors={"general": "We could not update this patient right now. %s" % exc},
                ),
            )

    @http.route(
        "/hospital/patient/<int:patient_id>/delete",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def delete_patient(self, patient_id, **post):
        patient = _find_patient(patient_id)
        if not patient:
            return _redirect_with_flash(
                "/hospital/my-patients",
                "That patient is unavailable or outside your account.",
                "err",
            )
        if _appointment_model().search_count([("patient_id", "=", patient.id)]):
            return _redirect_with_flash(
                "/hospital/my-patients",
                "Delete the patient's appointments before deleting the patient record.",
                "err",
            )
        try:
            patient.unlink()
            return _redirect_with_flash("/hospital/my-patients", "Patient deleted successfully.", "ok")
        except (ValidationError, UserError) as exc:
            return _redirect_with_flash("/hospital/my-patients", str(exc), "err")
        except Exception as exc:
            _logger.exception("website_hms: delete patient failed")
            return _redirect_with_flash(
                "/hospital/my-patients",
                "We could not delete this patient right now. %s" % exc,
                "err",
            )

    @http.route("/hospital/book-appointment", type="http", auth="user", website=True, methods=["GET"])
    def book_appointment_get(self, patient_id=None, **kw):
        form_data = None
        if patient_id:
            try:
                patient = _find_patient(int(patient_id))
            except Exception:
                patient = False
            if patient:
                form_data = _appointment_form_defaults()
                form_data["patient_id"] = str(patient.id)
        return request.render(
            "website_hms.tmpl_book_appt",
            _appointment_form_context(
                form_data=form_data,
                flash=kw.get("flash", ""),
                flash_type=kw.get("ft", "ok"),
            ),
        )

    @http.route(
        "/hospital/book-appointment/submit",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def book_appointment_post(self, **post):
        values, errors = _parse_appointment_values(post)
        if errors:
            return request.render(
                "website_hms.tmpl_book_appt",
                _appointment_form_context(form_data=post, errors=errors),
            )
        values["state"] = "draft"
        try:
            appointment = _appointment_model().create(values)
            return request.render("website_hms.tmpl_book_appt_success", {
                "appt": appointment,
                "is_admin": _is_hms_admin(),
            })
        except (ValidationError, UserError) as exc:
            return request.render(
                "website_hms.tmpl_book_appt",
                _appointment_form_context(form_data=post, errors={"general": str(exc)}),
            )
        except Exception as exc:
            _logger.exception("website_hms: create appointment failed")
            return request.render(
                "website_hms.tmpl_book_appt",
                _appointment_form_context(
                    form_data=post,
                    errors={"general": "We could not book this appointment right now. %s" % exc},
                ),
            )

    @http.route(
        "/hospital/appointment/<int:appointment_id>/edit",
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def edit_appointment_get(self, appointment_id, **kw):
        appointment = _find_appointment(appointment_id)
        if not appointment:
            return _redirect_with_flash(
                "/hospital/my-appointments",
                "That appointment is unavailable or outside your account.",
                "err",
            )
        return request.render(
            "website_hms.tmpl_book_appt",
            _appointment_form_context(
                record=appointment,
                flash=kw.get("flash", ""),
                flash_type=kw.get("ft", "ok"),
            ),
        )

    @http.route(
        "/hospital/appointment/<int:appointment_id>/update",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def edit_appointment_post(self, appointment_id, **post):
        appointment = _find_appointment(appointment_id)
        if not appointment:
            return _redirect_with_flash(
                "/hospital/my-appointments",
                "That appointment is unavailable or outside your account.",
                "err",
            )
        values, errors = _parse_appointment_values(post, record=appointment)
        if errors:
            return request.render(
                "website_hms.tmpl_book_appt",
                _appointment_form_context(record=appointment, form_data=post, errors=errors),
            )
        try:
            appointment.write(values)
            return _redirect_with_flash(
                "/hospital/my-appointments",
                "Appointment updated successfully.",
                "ok",
            )
        except (ValidationError, UserError) as exc:
            return request.render(
                "website_hms.tmpl_book_appt",
                _appointment_form_context(
                    record=appointment,
                    form_data=post,
                    errors={"general": str(exc)},
                ),
            )
        except Exception as exc:
            _logger.exception("website_hms: update appointment failed")
            return request.render(
                "website_hms.tmpl_book_appt",
                _appointment_form_context(
                    record=appointment,
                    form_data=post,
                    errors={"general": "We could not update this appointment right now. %s" % exc},
                ),
            )

    @http.route(
        "/hospital/appointment/<int:appointment_id>/delete",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def delete_appointment(self, appointment_id, **post):
        appointment = _find_appointment(appointment_id)
        if not appointment:
            return _redirect_with_flash(
                "/hospital/my-appointments",
                "That appointment is unavailable or outside your account.",
                "err",
            )
        try:
            appointment.unlink()
            return _redirect_with_flash(
                "/hospital/my-appointments",
                "Appointment deleted successfully.",
                "ok",
            )
        except (ValidationError, UserError) as exc:
            return _redirect_with_flash("/hospital/my-appointments", str(exc), "err")
        except Exception as exc:
            _logger.exception("website_hms: delete appointment failed")
            return _redirect_with_flash(
                "/hospital/my-appointments",
                "We could not delete this appointment right now. %s" % exc,
                "err",
            )
