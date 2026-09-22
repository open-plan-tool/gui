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
            location.reload();
        },
        // On Error
        function(data) {
            const modalBody = document.querySelector('#${modal_id} .modal-body');
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
