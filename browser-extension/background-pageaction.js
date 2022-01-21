function openDiscussionsURL(url, tab) {
    var creating = browser.tabs.create(
	{
	    'active': true,
	    'url': url,
	    'index': tab.index + 1,
	    /* 'openerTabId': tab.id, */
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


//browser.browserAction.onClicked.addListener(openDiscussionsURLCurrentTab);
browser.pageAction.onClicked.addListener(openDiscussionsURLCurrentTab);


api_base = 'https://discu.eu/api/v0';
api_token = 'browser-extension';


/*
    "browser_action": {
	"default_icon": "icons/favicon-32x32.png",
	"default_title": "Discussions"
    },
*/

/*
function _resetBadge(tabId) {
     browser.browserAction.setBadgeText({
	text: "",
	tabId: tabId,
    });

    browser.browserAction.setTitle({
	title: "",
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

    browser.browserAction.setBadgeText({
	text: count.toString(),
	tabId: tabId,
    });

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
*/

function _resetPageAction(tabId) {
    browser.pageAction.hide(tabId);
    /*
     browser.browserAction.setBadgeText({
	text: "",
	tabId: tabId,
    });

    browser.browserAction.setTitle({
	title: "",
	tabId: tabId,
    });
    */
}

function _setPageActionIcon(count, tabId) {
    var canvas = document.createElement('canvas');
    var img = document.createElement('img');
    img.onload = function () {
        var context = canvas.getContext('2d');
        context.drawImage(img, 0, 0, 16, 16);
	/*
        context.fillStyle = "rgba(255,0,0,1)";
        context.fillRect(10, 0, 19, 19);
*/
        context.fillStyle = "black";
        context.font = "9px Arial";
        context.fillText(count, 0, 19);

        browser.pageAction.setIcon({
            imageData: context.getImageData(0, 0, 19, 19),
            tabId:     tabId
        });
    };
    img.src = "icons/favicon-32x32.png";
}

function _updatePageAction(counts, tabId) {
    console.log("counts: ");
    console.log(tabId);
    console.log(counts);
    if (!counts || (!counts.total_discussions && !counts.articles_count)) {
	_resetPageAction(tabId);
	return;
    }

    let count = counts.total_comments + counts.articles_count;

    // _setPageActionIcon(count.toString(), tabId);

    try {
	console.log("set title");
	browser.pageAction.setTitle({
	    title: `${count} comments ${counts.total_discussions} discussions`,
	    tabId: tabId,
	}).then(console.log, console.error);
    } catch(error) {
	console.error(error);
    }

    console.log("show");
    browser.pageAction.show(tabId);
    console.log("end show");
}

function updatePageAction(url, tabId) {
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
	.then(counts => _updatePageAction(counts, tabId), e => console.error(e));
}


function updateTab(tabId, changeInfo, tab) {
    if (changeInfo.url) {
	updatePageAction(changeInfo.url, tabId);
    }
}

browser.tabs.onUpdated.addListener(updateTab);
