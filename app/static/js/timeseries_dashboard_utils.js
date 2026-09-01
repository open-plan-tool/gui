function getDataForTimeseriesSubmit() {
    const modal = document.getElementById('uploadTimeseriesModal');
    const form = modal.querySelector('form');
    const formData = new FormData(form);

    submitForm(
        postTimeseriesFormUrl,
        formData,
        // On Success
        function(data) {
            form.reset();
            const modal = bootstrap.Modal.getInstance(document.getElementById('uploadTimeseriesModal'));
            if (modal) modal.hide();
            location.reload();
        },
        // On Error
        function(data) {
            const modalBody = document.querySelector('#uploadTimeseriesModal .modal-body');
            if (data.form_html) {
                modalBody.innerHTML = data.form_html;
            } else {
                alert("Fehler: " + JSON.stringify(data.errors || data.error));
            }
        }
    );
}
