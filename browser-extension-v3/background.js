
console.log("loadaed");

function openDiscussionsURL(url, tab) {
	var creating = chrome.tabs.create(
		{
			'active': true,
			'url': url,
			'index': tab.index + 1,
			/* 'openerTabId': tab.id, */
		}
	).then((tab) => { }, console.error);
}

function openDiscussionsURLTabs(tabs) {
	for (const tab of tabs) {
		var url = 'https://discu.eu/?q=' + encodeURIComponent(tab.url) + '&submit_title=' + encodeURIComponent(tab.title) + '&utm_source=browser-extension';

		openDiscussionsURL(url, tab);
	}
}

function openDiscussionsURLCurrentTab() {
	chrome.tabs.query({ currentWindow: true, active: true })
		.then(openDiscussionsURLTabs,
			console.error);
};

chrome.action.onClicked.addListener(openDiscussionsURLCurrentTab);

api_base = 'https://discu.eu/api/v0';
api_token = 'browser-extension';

function _resetBadge(tabId) {
	chrome.action.setBadgeText({
		text: "",
		tabId: tabId,
	});
	chrome.action.setTitle({
		title: "Discussions",
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

	let count = counts.total_comments + counts.articles_count;

	if (count > 999) {
		count = 999;
	}

	chrome.action.setBadgeText({
		text: count.toString(),
		tabId: tabId,
	});
	chrome.action.setTitle({
		title: `${counts.total_discussions} Discussions `,
		tabId: tabId,
	});
	chrome.action.setBadgeBackgroundColor({
		color: '#666666',
		tabId: tabId,
	})
	chrome.action.setBadgeTextColor({
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

chrome.tabs.onUpdated.addListener(updateTab);
