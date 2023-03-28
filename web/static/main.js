

function mentionFormOnInput(event) {

    const div = document.querySelector('#mention_live_preview');
    const formElement = document.querySelector('#dashboard_mentions_form form');

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
            if (key == 'exclude_platforms') {
                value[key] = [val];
            } else {
                value[key] = val;
            }
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
    ).catch((err) => {
        div.innerHTML = "<p>Something went wrong, please retry in a few moments...</p>"
    });
}

document.addEventListener("DOMContentLoaded", function () {
    const div = document.querySelector('#mention_live_preview');
    if (!div) {
        return;
    }
    var input = document.querySelector('#button-id-live-preview-mention-rule');
    if (input) {
        input.addEventListener('click', mentionFormOnInput);
    }
});
