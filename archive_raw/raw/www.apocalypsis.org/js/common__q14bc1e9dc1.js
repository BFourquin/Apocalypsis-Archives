function popup(page,width,height) {
	window.open(page,'Apocalypsis', 'width=' + width + ',height=' + height + ',scrollbars=yes,resizable=yes');
}

function toggle_bloc(NomCalque) {
	if (document.getElementById(NomCalque).style.visibility == "visible") {
		document.getElementById(NomCalque).style.visibility = "hidden";
		document.getElementById(NomCalque).style.display = "none";
	} else {
		document.getElementById(NomCalque).style.visibility = "visible";
		document.getElementById(NomCalque).style.display = "block";
	}
}

function toggleElements(el) {
	$(el).toggle(500);
}

var tooltipDelay = null;
function show_info(item) {
	const $item = $(item);
	const $tooltip = $item.parent().children('.tooltip');
	tooltipDelay = window.setTimeout(function() {
		$tooltip.toggleClass('open', true);
	}, 50);
}

function hide_info(item) {
	clearTimeout(tooltipDelay);
	$(item).parent().children('.tooltip').toggleClass('open', false);
}

function toggle_state(elem) {
	document.getElementsByName(elem)[0].disabled = 1 - document.getElementsByName(elem)[0].disabled;
}

states = {};
function toolbar(tag, form_name, widget_name) {
	if (typeof states[tag] === 'undefined') {
		states[tag] = 0;
	}

	obj = eval('document.' + form_name + '.' + widget_name);
	if (obj.selectionEnd) {
		if ((obj.selectionEnd - obj.selectionStart) > 0) {
			obj.value = obj.value.substring(0, obj.selectionStart) + "[" + tag + "]" + obj.value.substring(obj.selectionStart, obj.selectionEnd) + "[/" + tag + "]" + obj.value.substring(obj.selectionEnd, obj.value.length);
		} else if (states[tag] == 0) {
			obj.value = obj.value.substring(0, obj.selectionStart) + "[" + tag + "]" + obj.value.substring(obj.selectionStart, obj.value.length);
			states[tag] = 1-states[tag];
		} else {
			obj.value = obj.value.substring(0, obj.selectionStart) + "[/" + tag + "]" + obj.value.substring(obj.selectionStart, obj.value.length);
			states[tag] = 1-states[tag];
		}
	} else if (states[tag] == 0) {
		obj.value = obj.value + "[" + tag + "]";
		states[tag] = 1-states[tag];
	} else {
		obj.value = obj.value + "[/" + tag + "]";
		states[tag] = 1-states[tag];
	}
}

function putvalue(form_name, widget_name, valeur) {
	obj = eval("document." + form_name + "." + widget_name);
	obj.value = valeur;
	obj.className = obj.className.replace(/\berror\b/g, "");
}

function set_cookie(name, value) {
	document.cookie = name + "=" + escape(value);
}

function get_cookie(name) {
	if (document.cookie) {
		index = document.cookie.indexOf(name);
		if (index != -1) {
			start = document.cookie.indexOf( "=", index) + 1;
			end = document.cookie.indexOf( ";", index);
			if (end == -1) end = document.cookie.length;
			return unescape(document.cookie.substring(start, end));
		}
	}
	return null;
}

function checkAll(elem, selector) {
	console.log(elem);
	var state = elem.checked;

	iesucks = $(selector).each(function(i, node) {
		node.checked = state;
	});
}

function open_left_comx() {
	$("#conversation_panel .comx.left fieldset").addClass('open');
	$("#conversation_panel .toogle .left_toogle_open").hide();
	$("#conversation_panel .toogle .left_toogle_close").show();
}
function open_right_comx() {
	$("#conversation_panel .comx.right fieldset").addClass('open');
	$("#conversation_panel .toogle .right_toogle_open").hide();
	$("#conversation_panel .toogle .right_toogle_close").show();
}
function close_left_comx() {
	$("#conversation_panel .comx.left fieldset").removeClass('open');
	$("#conversation_panel .toogle .left_toogle_close").hide();
	$("#conversation_panel .toogle .left_toogle_open").show();
}
function close_right_comx() {
	$("#conversation_panel .comx.right fieldset").removeClass('open');
	$("#conversation_panel .toogle .right_toogle_close").hide();
	$("#conversation_panel .toogle .right_toogle_open").show();
}

$( document ).ready(function() {
	$("#conversation_panel .comx legend").click(function() {
		$(this).parent('fieldset').toggleClass('open');
	});

	var $domElements = $('.autonumeric');
	if ($domElements.length && AutoNumeric !== undefined) {
		new AutoNumeric.multiple($domElements.toArray(), {
			watchExternalChanges: true,
			digitGroupSeparator: ' ',
			decimalCharacter: ',',
			decimalPlaces: 0,
			modifyValueOnWheel: false
		});
		$domElements.on('input', function () {
			var anElement = AutoNumeric.getAutoNumericElement(this);
			if (anElement && this.value.length > 0) {
				anElement.set(this.value, null, true);
			}
		});
	}
});

function selectall(formu)
{
    let iesucks = eval('document.form'+formu+'.getElementsByTagName("input")');
    for (let i = 1 ; i < iesucks.length ; i++)
    {
        iesucks[i].checked = iesucks[0].checked;
    }
}

function del_units(gal, sec, sys, coo, type)
{
    delete units[gal][sec][sys][coo][type];
    tr_render();
}