

function mentionFormOnInput(event) {

    const div = document.querySelector('#mention_live_preview');
    const formElement = document.querySelector('#dashboard_mentions_form_new form');

    const formData = new FormData(formElement);

    var value = {}
    for (const [key, val] of formData.entries()) {
        if (value[key]) {
            if (value[key] instanceof Array) {
                value[key].push(val)
            } else {
                value[key] = [value[key], val]
            }

        } else {
            value[key] = val;
        }
    }

    div.innerHTML = '<p>Looking results up...</p>'

    fetch("/mention_live_preview",
        {
            credentials: "same-origin",
            body: JSON.stringify(value),
            method: "POST",
            cache: "no-cache",
            headers: {
                "Content-Type": "application/json",
            },
        }
    ).then((response) =>
        response.text()
    ).then((body) =>
        div.innerHTML = body
    );
}

document.addEventListener("DOMContentLoaded", function () {
    const div = document.querySelector('#mention_live_preview');
    if (!div) {
        return;
    }
    for (let input of document.querySelectorAll('#dashboard_mentions_form_new input')) {
        input.addEventListener('input', mentionFormOnInput)
    }

});
