javascript: (function () {
    var url = 'https://discu.eu/?q=' + encodeURIComponent(document.title) + '&submit_url=' + encodeURIComponent(window.location.href);
    var win = window.open(url, '_blank');
    win.focus();
})();