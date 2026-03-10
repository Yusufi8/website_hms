# -*- coding: utf-8 -*-
{
    "name": "YK Hospital Website Portal",
    "summary": "Premium hospital website and patient portal for hospital_yk",
    "version": "18.0.4.0.0",
    "author": "Yusuf Khan",
    "license": "LGPL-3",
    "category": "Healthcare/Website",
    "depends": [
        "base",
        "web",
        "hospital_yk",
        "hr",
        "website",
        "portal",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/hms_portal_rules.xml",
        "views/website_menu.xml",
        "views/tmpl_home.xml",
        "views/tmpl_dashboard.xml",
        "views/tmpl_portal.xml",
        "views/tmpl_patient.xml",
        "views/tmpl_appointment.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "website_hms/static/src/css/hms_portal.css",
            "website_hms/static/src/js/hms_portal.js",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
