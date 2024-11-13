// Disable Mouse scrolling on numbers inputs
$(document).on("wheel", "input[type=number]", function (e) {
    $(this).blur();
});

// Add a highligh class when a value of the form is changed
$(".form-group :input").each(function(){
    var input_tag = $(this);
    // apply this only if the value is not empty
    if (input_tag[0].value !== ""){
        input_tag.on('keydown', function () {
            $(this).addClass('highlight');
        });
    }
});
