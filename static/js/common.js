var API = '';
var _csrfToken = '';

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    var str = String(text);
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

function escapeAttr(text) {
    if (text === null || text === undefined) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function safeOnclick(handlerName, ...args) {
    var escapedArgs = args.map(arg => 
        typeof arg === 'string' ? encodeURIComponent(arg) : arg
    );
    return `${handlerName}(${escapedArgs.join(', ')})`;
}

function getCsrfToken() {
    return _csrfToken || (document.cookie.match(/_csrf_token=([^;]+)/) || [])[1] || '';
}

$(document).ajaxSend(function(event, xhr, settings) {
    var csrfToken = getCsrfToken();
    if (csrfToken && settings.type && settings.type.toUpperCase() !== 'GET') {
        xhr.setRequestHeader('X-CSRFToken', csrfToken);
    }
});

$(document).ajaxComplete(function(event, xhr, settings) {
    var csrfToken = xhr.getResponseHeader('X-CSRFToken');
    if (csrfToken) {
        _csrfToken = csrfToken;
    }
});

function apiGet(url, callback, errorCallback) {
    $.ajax({
        url: API + url,
        type: 'GET',
        xhrFields: { withCredentials: true },
        success: function(res) {
            if (res.code === 401) { window.location.href = 'login.html'; return; }
            callback(res);
        },
        error: function(xhr) { 
            if (xhr.status === 401) { window.location.href = 'login.html'; return; }
            if (errorCallback) errorCallback(xhr);
        }
    });
}

function apiPost(url, data, callback, errorCallback) {
    $.ajax({
        url: API + url, type: 'POST', contentType: 'application/json',
        data: JSON.stringify(data), xhrFields: { withCredentials: true },
        success: function(res) {
            if (res.code === 401) { window.location.href = 'login.html'; return; }
            callback(res);
        },
        error: function(xhr) {
            if (xhr.status === 401) { window.location.href = 'login.html'; return; }
            if (errorCallback) errorCallback(xhr);
        }
    });
}

function apiPut(url, data, callback, errorCallback) {
    $.ajax({
        url: API + url, type: 'PUT', contentType: 'application/json',
        data: JSON.stringify(data), xhrFields: { withCredentials: true },
        success: function(res) {
            if (res.code === 401) { window.location.href = 'login.html'; return; }
            callback(res);
        },
        error: function(xhr) { 
            if (xhr.status === 401) { window.location.href = 'login.html'; return; }
            if (errorCallback) errorCallback(xhr);
        }
    });
}

function apiDelete(url, callback, errorCallback) {
    $.ajax({
        url: API + url, type: 'DELETE', xhrFields: { withCredentials: true },
        success: function(res) {
            if (res.code === 401) { window.location.href = 'login.html'; return; }
            callback(res);
        },
        error: function(xhr) { 
            if (xhr.status === 401) { window.location.href = 'login.html'; return; }
            if (errorCallback) errorCallback(xhr);
        }
    });
}

function showToast(msg, type) {
    type = type || 'info';
    var cls = 'alert-info';
    if (type === 'success') cls = 'alert-success';
    if (type === 'error') cls = 'alert-danger';
    var $t = $('<div class="alert ' + cls + '" style="position:fixed;top:20px;right:20px;z-index:9999;min-width:200px;">' + msg + '</div>');
    $('body').append($t);
    setTimeout(function() { $t.fadeOut(300, function() { $t.remove(); }); }, 2500);
}

function checkLogin(callback) {
    apiGet('/api/user/info', function(res) {
        if (res.code === 200) {
            $('#username').text(res.data.username);
            $('#userRole').text(res.data.role === 'admin' ? '管理员' : '操作员');
            if (callback) callback(res.data);
        }
    });
}

function renderPagination(container, total, page, perPage, onPageChange) {
    var totalPages = Math.ceil(total / perPage);
    var html = '<div class="pagination-info">';
    html += '共 <b>' + total + '</b> 条 &nbsp; 第 <b>' + page + '</b>/' + totalPages + ' 页';
    if (totalPages > 1) {
        html += ' &nbsp; 跳至 <input type="number" class="page-jump-input" min="1" max="' + totalPages + '" value="" onkeydown="if(event.keyCode===13){var v=parseInt(this.value);if(v>=1&&v<=' + totalPages + '){' + onPageChange + '(v);}}"> 页';
        html += ' <button class="page-jump-btn" onclick="var inp=this.previousElementSibling;var v=parseInt(inp.value);if(v>=1&&v<=' + totalPages + '){' + onPageChange + '(v);}">跳转</button>';
    }
    html += '</div>';
    if (totalPages <= 1) { $(container).html(html); return; }
    html += '<div class="page-btns">';
    html += '<button ' + (page <= 1 ? 'disabled' : '') + ' onclick="' + onPageChange + '(1)">首页</button>';
    html += '<button ' + (page <= 1 ? 'disabled' : '') + ' onclick="' + onPageChange + '(' + (page - 1) + ')">上一页</button>';
    var start = Math.max(1, page - 2);
    var end = Math.min(totalPages, page + 2);
    if (start > 1) { html += '<button onclick="' + onPageChange + '(1)">1</button>'; if (start > 2) html += '<span class="page-ellipsis">...</span>'; }
    for (var i = start; i <= end; i++) {
        html += '<button class="' + (i === page ? 'active' : '') + '" onclick="' + onPageChange + '(' + i + ')">' + i + '</button>';
    }
    if (end < totalPages) { if (end < totalPages - 1) html += '<span class="page-ellipsis">...</span>'; html += '<button onclick="' + onPageChange + '(' + totalPages + ')">' + totalPages + '</button>'; }
    html += '<button ' + (page >= totalPages ? 'disabled' : '') + ' onclick="' + onPageChange + '(' + (page + 1) + ')">下一页</button>';
    html += '<button ' + (page >= totalPages ? 'disabled' : '') + ' onclick="' + onPageChange + '(' + totalPages + ')">末页</button>';
    html += '</div>';
    $(container).html(html);
}

function getQueryParam(name) {
    var reg = new RegExp('(^|&)' + name + '=([^&]*)(&|$)');
    var r = window.location.search.substr(1).match(reg);
    return r ? decodeURIComponent(r[2]) : '';
}

function buildSidebar(activePage) {
    var isAdmin = window._userRole === 'admin';
    var navItems = [
        { id: 'dashboard', href: 'index.html', icon: '&#9776;', text: '系统首页' },
        { id: 'staff_manage', href: 'staff_manage.html', icon: '&#128100;', text: '人员档案' },
        { id: 'salary_book', href: 'salary_book.html', icon: '&#128218;', text: '薪酬帐套', admin: true },
        { id: 'salary_calc', href: 'salary_calc.html', icon: '&#128176;', text: '薪资核算', admin: true },
        { id: 'salary_query', href: 'salary_query.html', icon: '&#128269;', text: '薪资查询' },
        { id: 'export', href: 'export.html', icon: '&#128229;', text: '报表导出' },
        { id: 'settings', href: 'settings.html', icon: '&#9881;', text: '系统设置', admin: true }
    ];

    var html = '<div class="sidebar-brand"><h3>薪酬管理系统</h3><small>人员薪资核算平台</small></div><nav class="sidebar-nav">';
    for (var i = 0; i < navItems.length; i++) {
        var item = navItems[i];
        if (item.admin && !isAdmin) continue;
        var cls = item.id === activePage ? ' active' : '';
        html += '<a href="' + item.href + '" class="' + cls + '"><span class="nav-icon">' + item.icon + '</span>' + item.text + '</a>';
    }
    html += '</nav>';
    $('.sidebar').html(html);
}

function initPage(activePage) {
    checkLogin(function(data) {
        window._userRole = data.role;
        buildSidebar(activePage);
        if ($('.user-info').length && !$('#btnChangePwd').length) {
            var $btn = $('<button class="btn btn-sm btn-primary" id="btnChangePwd" onclick="showPwdModal()">改密</button>');
            $('.user-info #username').after($btn);
            var $modal = $('<div id="pwdModal" style="display:none;"><div class="modal-overlay"><div class="modal" style="width:420px;"><div class="modal-header"><h4>修改密码</h4><button class="close-btn" onclick="$(\'#pwdModal\').hide()">&times;</button></div><div class="modal-body"><div class="form-group"><label>原密码</label><input type="password" class="form-control" id="cpOldPwd"></div><div class="form-group"><label>新密码</label><input type="password" class="form-control" id="cpNewPwd"></div><div class="form-group"><label>确认新密码</label><input type="password" class="form-control" id="cpConfirmPwd"></div></div><div class="modal-footer"><button class="btn btn-outline" onclick="$(\'#pwdModal\').hide()">取消</button><button class="btn btn-primary" onclick="doChangePassword()">确认修改</button></div></div></div></div>');
            $('body').append($modal);
        }
    });
}

function logout() {
    apiPost('/api/logout', {}, function() { window.location.href = 'login.html'; });
}

function showPwdModal() {
    $('#cpOldPwd').val('');
    $('#cpNewPwd').val('');
    $('#cpConfirmPwd').val('');
    $('#pwdModal').show();
}

function doChangePassword() {
    var oldPwd = $('#cpOldPwd').val();
    var newPwd = $('#cpNewPwd').val();
    var confirmPwd = $('#cpConfirmPwd').val();
    if (!oldPwd || !newPwd) { showToast('请填写完整', 'error'); return; }
    if (newPwd !== confirmPwd) { showToast('两次密码不一致', 'error'); return; }
    apiPost('/api/user/change_password', { old_password: oldPwd, new_password: newPwd }, function(res) {
        if (res.code === 200) {
            showToast('密码修改成功', 'success');
            $('#pwdModal').hide();
        } else {
            showToast(res.msg, 'error');
        }
    });
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

(function($) {
    $.fn.searchSelect = function(options) {
        var settings = $.extend({
            data: [],
            placeholder: '请选择',
            searchPlaceholder: '搜索...',
            value: '',
            onChange: null,
            width: ''
        }, options);

        return this.each(function() {
            var $container = $(this);
            $container.addClass('search-select');
            if (settings.width) $container.css('width', settings.width);

            var selectedValue = settings.value || '';
            var selectedText = '';

            var items = settings.data || [];
            for (var i = 0; i < items.length; i++) {
                if (items[i].value === selectedValue) {
                    selectedText = items[i].text || items[i].value;
                    break;
                }
            }

            var $input = $('<input type="text" class="ss-input" readonly placeholder="' + settings.placeholder + '">');
            $input.val(selectedText || '');
            $container.append($input);

            var $dropdown = $('<div class="ss-dropdown"></div>');
            var $searchBox = $('<div class="ss-search"><input type="text" placeholder="' + settings.searchPlaceholder + '"></div>');
            var $optionsList = $('<div class="ss-options"></div>');
            $dropdown.append($searchBox).append($optionsList);
            $container.append($dropdown);

            function renderOptions(filter) {
                filter = (filter || '').toLowerCase();
                var html = '';
                var hasVisible = false;
                for (var i = 0; i < items.length; i++) {
                    var item = items[i];
                    var text = item.text || item.value;
                    if (filter && text.toLowerCase().indexOf(filter) === -1) continue;
                    var sel = item.value === selectedValue ? ' selected' : '';
                    html += '<div class="ss-option' + sel + '" data-value="' + item.value + '">' + text + '</div>';
                    hasVisible = true;
                }
                if (!hasVisible) {
                    html = '<div class="ss-empty">无匹配项</div>';
                }
                $optionsList.html(html);
            }

            renderOptions();

            $input.on('click focus', function(e) {
                e.stopPropagation();
                $('.search-select .ss-dropdown.open').not($dropdown).removeClass('open');
                $dropdown.addClass('open');
                $searchBox.find('input').val('').focus();
                renderOptions();
            });

            $searchBox.on('click', function(e) { e.stopPropagation(); });

            $searchBox.on('input', 'input', function() {
                renderOptions($(this).val());
            });

            $optionsList.on('click', '.ss-option', function() {
                var val = $(this).data('value');
                var text = $(this).text();
                selectedValue = val;
                selectedText = text;
                $input.val(text);
                $dropdown.removeClass('open');
                $container.data('value', val);
                if (settings.onChange) settings.onChange(val, text);
            });

            $(document).on('click', function() {
                $dropdown.removeClass('open');
            });

            $container.data('value', selectedValue);

            $container[0].setValue = function(val) {
                selectedValue = val;
                for (var i = 0; i < items.length; i++) {
                    if (items[i].value === val) {
                        selectedText = items[i].text || items[i].value;
                        break;
                    }
                }
                $input.val(selectedText || '');
                $container.data('value', val);
            };

            $container[0].setOptions = function(newData) {
                items = newData || [];
                renderOptions();
            };

            $container[0].getValue = function() {
                return selectedValue;
            };
        });
    };
})(jQuery);

function confirmDelete(actionName, callback) {
    if (confirm('⚠️ 确定要' + actionName + '吗？\n\n此操作不可撤销！')) {
        if (callback) callback();
    }
}

$(document).ajaxComplete(function(event, xhr, settings) {
    if (xhr.status === 401 && !settings.url.includes('/api/user/info')) {
        window.location.href = 'login.html';
        return;
    }
    
    if (xhr.status >= 500 && xhr.status < 600) {
        showToast('服务器繁忙，请稍后重试', 'error');
    }
});

function apiCall(method, url, data, successCallback, failCallback) {
    var config = {
        url: API + url,
        type: method,
        xhrFields: { withCredentials: true },
        success: function(res) {
            if (res.code === 401) {
                window.location.href = 'login.html';
                return;
            }
            if (res.code === 200) {
                if (successCallback) successCallback(res.data);
            } else {
                if (failCallback) failCallback(res);
                else showToast(res.msg || '操作失败', 'error');
            }
        },
        error: function(xhr) {
            if (xhr.status === 401) {
                window.location.href = 'login.html';
                return;
            }
            
            var errorMsg = '网络错误';
            try {
                var response = JSON.parse(xhr.responseText);
                errorMsg = response.msg || errorMsg;
            } catch(e) {}
            
            showToast(errorMsg, 'error');
            if (failCallback) failCallback({code: xhr.status, msg: errorMsg});
        }
    };
    
    if (data && method !== 'GET') {
        config.contentType = 'application/json';
        config.data = JSON.stringify(data);
    }
    
    $.ajax(config);
}
