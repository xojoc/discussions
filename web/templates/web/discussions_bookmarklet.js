javascript: (function () {
    var url = 'https://discu.eu/?q=' + encodeURIComponent(window.location.href) + '&submit_title=' + encodeURIComponent(document.title) + '&utm_source=bookmarklet';
    var win = window.open(url, '_blank');
    win.focus();
})();
