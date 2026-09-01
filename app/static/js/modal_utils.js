    function submitModalForm(event, modalId=""){
        const submitFormBtn = document.getElementById(modalId + "SubmitBtn");
        submitFormBtn.click();
    }


    function showModal(event, modalId="", attrs = null){
        var modalInstance = $("#" + modalId);
        // update the attributes of the form tag of the modal
        for (const [key, value] of Object.entries(attrs)) {
            if(value){
                modalInstance.find('.modal-body form').attr(key, value)
            }
        }
         modalInstance.modal("show")
    }

    function submitForm(url, formData, onSuccess, onError) {
        fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: formData,
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                onSuccess(data);
            } else {
                onError(data);
            }
        })
        .catch(error => {
            console.error('AJAX Error:', error);
            onError({ error: error.message || "Netzwerkfehler" });
        });
    }
