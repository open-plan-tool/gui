function handleTimeseriesForm(send_to_url, modal_id) {
    // send_to_url: url that receives the form data and returns success or form with errors
    // takes a modal and selects its form and sends the data to the receiving view
    const modal = document.getElementById(modal_id);
    const form = modal.querySelector('form');
    const formData = new FormData(form);

    submitForm(
        send_to_url,
        formData,
        // On Success
        function(data) {
            form.reset();
            const modal = bootstrap.Modal.getInstance(document.getElementById(modal_id));
            if (modal) modal.hide();

            const table_body = document.getElementById("timeseries_table_body");
            if (table_body && data.table_html) {
                table_body.outerHTML = data.table_html;
                htmx.process(document.getElementById("timeseries_table_body"));
            }
            const details_panel = document.getElementById("timeseries_details_panel");
            if (details_panel && data.details_html) {
                details_panel.outerHTML = data.details_html;
                htmx.process(document.getElementById("timeseries_details_panel"));
            }
        },
        // On Error
        function(data) {
            const modalBody = document.querySelector(`#${modal_id} .modal-body`);
            if (data.form_html) {
                modalBody.innerHTML = data.form_html;
            } else {
                alert("Fehler: " + JSON.stringify(data.errors || data.error));
            }
        }
    );
}

function setEditTimeseriesUrl(timeseriesUrl) {
    editTimeseriesFormUrl = timeseriesUrl;
}

function getEditTimeseriesForm(event) {
    event.preventDefault();
    const modal = document.getElementById("editTimeseriesModal");

    fetch(editTimeseriesFormUrl, {
        method: "GET",
        headers: {
            "X-Requested-With": "XMLHttpRequest"
        }
    }).then(response => {
        if (!response.ok) {
            throw new Error("Failed to load the form.");
        }
        return response.text();
    }).then(formHtml => {
        const modalBody = modal.querySelector(".modal-body");
        modalBody.innerHTML = formHtml;
        showModal(event, "editTimeseriesModal");
    }).catch(error => {
        console.error("Failed to show Modal with form:", error);
    });
}

// listening for click on "add timeseries", handles dropdown
document.addEventListener("DOMContentLoaded", function () {
    const wrapper = document.getElementById("addTimeseries");
    const btn = document.getElementById("addTimeseriesBtn");

    btn.addEventListener("click", function (e) {
        e.stopPropagation();
        wrapper.classList.toggle("open");
    });

    document.addEventListener("click", function (e) {
        if (!wrapper.contains(e.target)) {
            wrapper.classList.remove("open");
        }
    });

    document.querySelectorAll(".dropdown-menu-custom button").forEach(function (item) {
        item.addEventListener("click", function () {
            wrapper.classList.remove("open");
        });
    });
});

// handling the plot inside detail-panel
function plotSelectedTimeseries() {
    const plotDiv = document.getElementById("ts_detail_plot");
    if (!plotDiv) return;
    const tsId = plotDiv.dataset.tsId;
    if (!tsId) return;

    fetch(`${tsValuesUrl}/${tsId}`)
        .then(resp => resp.json())
        .then(data => {
            const values = data["values"];
            if (!Array.isArray(values) || values.length === 0) {
                plotDiv.textContent = "No values available.";
                return;
            }
            const start = plotDiv.dataset.tsStart ? new Date(plotDiv.dataset.tsStart) : null;
            const x = start && !isNaN(start)
                ? values.map((_, i) => new Date(start.getTime() + i * 3600_000).toISOString())
                : values.map((_, i) => i);
            makePlotly(x, values, "ts_detail_plot");
        })
        .catch(err => {
            plotDiv.textContent = "Could not load timeseries values.";
            console.error(err);
        });
}
// initial load (full page render)
plotSelectedTimeseries();
// after every htmx swap into the details panel
document.body.addEventListener("htmx:afterSwap", (e) => {
    if (e.detail.target.id === "timeseries_details_panel") {
        plotSelectedTimeseries();
    }
});
