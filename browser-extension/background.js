function openDiscussionsURL(url, tab) {
    var creating = browser.tabs.create(
	{
	    'active': true,
	    'url': url,
	    'index': tab.index + 1,
	    'openerTabId': tab.id,
	}
    ).then((tab) => {}, console.error);
}

function openDiscussionsURLTabs(tabs) {
    for (const tab of tabs) {
	var url = 'https://discu.eu/?q=' + encodeURIComponent(tab.url) + '&submit_title=' + encodeURIComponent(tab.title);

	openDiscussionsURL(url, tab);
    }
}

function openDiscussionsURLCurrentTab() {
    browser.tabs.query({currentWindow: true, active: true})
	.then(openDiscussionsURLTabs,
	      console.error);
};


browser.browserAction.onClicked.addListener(openDiscussionsURLCurrentTab);

api_base = 'https://discu.eu/api/v0';
api_token = 'browser-extension';

function _resetBadge(tabId) {
     browser.browserAction.setBadgeText({
	text: null,
	tabId: tabId,
    });

    browser.browserAction.setTitle({
	title: null,
	tabId: tabId,
    });
}

function _updateBadge(counts, tabId) {
    console.log("counts: ");
    console.log(tabId);
    console.log(counts);
    if (!counts || (!counts.total_discussions && !counts.articles_count)) {
	_resetBadge(tabId);
	return;
    }

    browser.browserAction.setBadgeText({
	text: counts.total_comments.toString(),
	tabId: tabId,
    });

    let count = counts.total_comments + counts.articles_count;

    browser.browserAction.setTitle({
	title: `Comments ${count} Discussions ${counts.total_discussions}`,
	tabId: tabId,
    });

    browser.browserAction.setBadgeBackgroundColor({
	color: '#666666',
	tabId: tabId,
    })
    browser.browserAction.setBadgeTextColor({
	color: "white",
	tabId: tabId,
    })
}

function updateBadge(url, tabId) {
    if (!url) {
	return;
    }

    var u = api_base + '/discussion_counts/url/' + encodeURIComponent(url);
    var res = fetch(u, {
	headers: new Headers({
	    'accept': 'application/json',
	    'Authorization': 'Bearer ' + api_token,
	})
    })
	.then(response => response.json(), e => console.error(e))
	.then(counts => _updateBadge(counts, tabId), e => console.error(e));
}

function updateTab(tabId, changeInfo, tab) {
    if (changeInfo.url) {
	updateBadge(changeInfo.url, tabId);
    }
}

browser.tabs.onUpdated.addListener(updateTab);
