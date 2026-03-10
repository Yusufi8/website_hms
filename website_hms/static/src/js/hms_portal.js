(function () {
    "use strict";

    function revealSections() {
        var nodes = document.querySelectorAll(
            ".hms-feature-card, .hms-step-card, .hms-metric-card, .hms-data-card, .hms-form-card, .hms-side-card, .hms-empty-state, .hms-admin-gateway"
        );
        nodes.forEach(function (node, index) {
            node.classList.add("hms-reveal");
            requestAnimationFrame(function () {
                setTimeout(function () {
                    node.classList.add("is-visible");
                }, index * 40);
            });
        });
    }

    function autoDismissAlerts() {
        var alerts = document.querySelectorAll(".hms-alert");
        alerts.forEach(function (alert) {
            setTimeout(function () {
                alert.style.transition = "opacity .35s ease, transform .35s ease";
                alert.style.opacity = "0";
                alert.style.transform = "translateY(-6px)";
                setTimeout(function () {
                    alert.remove();
                }, 360);
            }, 4200);
        });
    }

    function bindConfirmButtons() {
        var buttons = document.querySelectorAll("[data-hms-confirm]");
        buttons.forEach(function (button) {
            button.addEventListener("click", function (event) {
                var message = button.getAttribute("data-hms-confirm") || "Are you sure?";
                if (!window.confirm(message)) {
                    event.preventDefault();
                }
            });
        });
    }

    function highlightHospitalNav() {
        var currentPath = window.location.pathname;
        var navLinks = document.querySelectorAll("#top_menu a[href], .o_navbar_mobile a[href]");
        navLinks.forEach(function (link) {
            try {
                if (currentPath.indexOf("/hospital") === 0 && link.pathname === "/hospital") {
                    link.style.fontWeight = "700";
                    link.style.color = "#1357c5";
                }
            } catch (error) {
                return;
            }
        });
    }

    function setFooterYear() {
        var target = document.getElementById("hms-year");
        if (target) {
            target.textContent = new Date().getFullYear();
        }
    }

    function init() {
        revealSections();
        autoDismissAlerts();
        bindConfirmButtons();
        highlightHospitalNav();
        setFooterYear();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
