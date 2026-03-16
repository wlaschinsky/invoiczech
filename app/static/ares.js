/**
 * Sdílená logika pro práci s kontakty a ARES.
 *
 * Očekává v DOM:
 *   #contact_id   — <select> s kontakty (data-ico, data-name, data-dic, ...)
 *   #ares_ico      — <input> pro IČO
 *   #ares-status   — <div> pro zobrazení stavu (upozornění, tlačítko uložit)
 *
 * Pole pro vyplnění (volitelná — pokud neexistují, přeskočí se):
 *   #contact_name, #contact_ico, #contact_dic,
 *   #contact_street, #contact_zip, #contact_city
 */

/* ---------- helpers ---------- */

function _setVal(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val || '';
}

function _fillContactFields(data) {
  _setVal('contact_name', data.name);
  _setVal('contact_ico', data.ico);
  _setVal('contact_dic', data.dic);
  _setVal('contact_street', data.street);
  _setVal('contact_zip', data.zip_code);
  _setVal('contact_city', data.city);
}

function _selectContactInDropdown(id) {
  const sel = document.getElementById('contact_id');
  if (sel) sel.value = id;
}

function _findContactByIco(ico) {
  const sel = document.getElementById('contact_id');
  if (!sel) return null;
  for (const opt of sel.options) {
    if (opt.dataset.ico === ico) return opt;
  }
  return null;
}

function _showStatus(html) {
  const box = document.getElementById('ares-status');
  if (box) box.innerHTML = html;
}

function _clearStatus() {
  _showStatus('');
}

/* ---------- veřejné funkce ---------- */

function fillContactFromSelect(sel) {
  const opt = sel.options[sel.selectedIndex];
  if (!opt || !opt.value) return;
  _fillContactFields({
    name: opt.dataset.name,
    ico: opt.dataset.ico,
    dic: opt.dataset.dic,
    street: opt.dataset.street,
    zip_code: opt.dataset.zip,
    city: opt.dataset.city,
  });
  _clearStatus();
}

async function loadFromAres() {
  const ico = document.getElementById('ares_ico').value.trim();
  if (!ico) { alert('Zadejte IČO'); return; }

  _showStatus('<span class="text-muted">Načítám…</span>');

  try {
    const resp = await fetch(`/adresar/ares/${ico}`);
    const data = await resp.json();
    if (data.error) {
      _showStatus(`<span class="text-danger">ARES: ${data.error}</span>`);
      return;
    }

    if (data.source === 'adresar') {
      // Kontakt už existuje v adresáři
      const opt = _findContactByIco(data.ico);
      if (opt) {
        _selectContactInDropdown(opt.value);
        fillContactFromSelect(document.getElementById('contact_id'));
      } else {
        _fillContactFields(data);
      }
      _showStatus('<span class="text-success">Kontakt nalezen v adresáři</span>');
    } else {
      // Nový kontakt z ARES — vyplnit pole a nabídnout uložení
      document.getElementById('contact_id').value = '';
      _fillContactFields(data);
      _showStatus(
        '<span class="text-success">Načteno z ARES</span> ' +
        '<button type="button" class="btn btn-sm btn-secondary" ' +
        'onclick="saveAresContact()">Uložit do adresáře</button>'
      );
      // Uložit data pro pozdější uložení
      window._aresData = data;
    }
  } catch(e) {
    _showStatus('<span class="text-danger">Chyba při komunikaci s ARES</span>');
  }
}

async function saveAresContact() {
  const data = window._aresData;
  if (!data || !data.ico) return;

  try {
    const resp = await fetch('/adresar/ares/ulozit', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data),
    });
    const result = await resp.json();
    if (result.error) {
      _showStatus(`<span class="text-danger">${result.error}</span>`);
      return;
    }

    // Přidat novou option do dropdownu a vybrat ji
    const sel = document.getElementById('contact_id');
    if (sel) {
      const opt = document.createElement('option');
      opt.value = result.id;
      opt.textContent = result.name + (data.ico ? ` (${data.ico})` : '');
      opt.dataset.name = data.name || '';
      opt.dataset.ico = data.ico || '';
      opt.dataset.dic = data.dic || '';
      opt.dataset.street = data.street || '';
      opt.dataset.zip = data.zip_code || '';
      opt.dataset.city = data.city || '';
      opt.dataset.email = data.email || '';
      sel.appendChild(opt);
      sel.value = result.id;
    }

    _showStatus('<span class="text-success">Uloženo do adresáře</span>');
    window._aresData = null;
  } catch(e) {
    _showStatus('<span class="text-danger">Chyba při ukládání</span>');
  }
}
