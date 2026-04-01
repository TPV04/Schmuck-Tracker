// ═══════════════════════════════════════════════════════════════
// SchmuckBot WebApp v8.0 - Gelddruckmaschine2.4 Integration
// Schreibt Haeuser/Schliessfach/Preis direkt in die richtigen Zellen
// Deployed: AKfycbxGlg34829lBHLf1zy63b-vkmu2ji_TSeoHqDLBqtO6a36p1TjB244p1pB6KxIOTbzF
// ═══════════════════════════════════════════════════════════════

const SHEET_GDM24       = "Gelddruckmaschine2.4";
const SHEET_PREIS_LIVE  = "Schmuck_Live";
const SHEET_HOUSES_RAW  = "Houses_Raw";
const SHEET_LOG         = "Bot_Log";

// Spalten in Gelddruckmaschine2.4 (0-basiert)
// G=6=Eisen, I=8=Dia, K=10=Gold, M=12=Schmuck
const COL_EISEN   = 6;   // G
const COL_DIA     = 8;   // I
const COL_GOLD    = 10;  // K
const COL_SCHMUCK = 12;  // M
const COL_NAME    = 1;   // B

// Ziv-Schliessfach -> Zeile 9, Gang -> Zeile 10
// Haeuser werden per Name-Match in Spalte B gefunden

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    if (data.action === "update_schmuck") {
      schreibeHousesRaw(data.haeuser, data.schliessfach, data.zeitstempel);
      schreibeSchmuckPreisLive(data.schmuck_preis, data.zeitstempel);
      updateGelddruckmaschine24(data.haeuser, data.schliessfach, data.schmuck_preis);
      schreibeLog("OK", data.zeitstempel,
        "h=" + (data.haeuser||[]).length + " f=" + (data.schliessfach||[]).length +
        " p=" + data.schmuck_preis);
      return ContentService.createTextOutput(JSON.stringify({status:"ok"}))
        .setMimeType(ContentService.MimeType.JSON);
    }
    return ContentService.createTextOutput(JSON.stringify({status:"unknown"}))
      .setMimeType(ContentService.MimeType.JSON);
  } catch(err) {
    schreibeLog("FEHLER", new Date().toLocaleString("de-DE"), err.toString());
    return ContentService.createTextOutput(JSON.stringify({status:"error",msg:err.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({status:"online",version:"8.0"}))
    .setMimeType(ContentService.MimeType.JSON);
}

function updateGelddruckmaschine24(haeuser, schliessfach, schmuckPreis) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(SHEET_GDM24);
  if (!sheet) return;

  const data = sheet.getDataRange().getValues();

  // Name->Zeile Map aus Spalte B
  const nameMap = {};
  data.forEach(function(row, i) {
    const n = row[COL_NAME] ? row[COL_NAME].toString().trim().toLowerCase() : '';
    if (n.length > 1) nameMap[n] = i + 1;
  });

  function getWert(items, name) {
    if (!items) return 0;
    for (let i = 0; i < items.length; i++) {
      if (items[i].name && items[i].name.toLowerCase() === name.toLowerCase())
        return parseInt(items[i].amount) || 0;
    }
    return 0;
  }

  function setzeSpalten(row, items) {
    const e = getWert(items, 'Eisenbarren');
    const d = getWert(items, 'Diamanten');
    const g = getWert(items, 'Goldbrikett');
    const s = getWert(items, 'Schmuck');
    sheet.getRange(row, COL_EISEN + 1).setValue(e);
    sheet.getRange(row, COL_DIA + 1).setValue(d);
    sheet.getRange(row, COL_GOLD + 1).setValue(g);
    sheet.getRange(row, COL_SCHMUCK + 1).setValue(s);
    Logger.log("Zeile " + row + " E=" + e + " D=" + d + " G=" + g + " S=" + s);
  }

  // Schliessfach
  if (schliessfach) {
    schliessfach.forEach(function(fach) {
      const t = fach.type ? fach.type.toLowerCase() : '';
      const row = t.includes('ziv') ? 9 : (t.includes('gang') ? 10 : null);
      if (row) setzeSpalten(row, fach.items);
    });
  }

  // Haeuser
  if (haeuser) {
    haeuser.forEach(function(haus) {
      if (!haus.items || !haus.items.length) return;
      const owner = haus.owner ? haus.owner.trim() : '';
      const loc   = haus.location ? haus.location.trim() : '';

      let row = null;
      // Direkter Match
      const keys = [owner.toLowerCase(), loc.toLowerCase(),
                    owner.split(' ')[0].toLowerCase(), loc.split(' ')[0].toLowerCase()];
      for (let k of keys) {
        if (nameMap[k]) { row = nameMap[k]; break; }
        // Partial
        for (let mk of Object.keys(nameMap)) {
          if (mk.includes(k) || k.includes(mk)) { row = nameMap[mk]; break; }
        }
        if (row) break;
      }

      if (row) {
        setzeSpalten(row, haus.items);
        Logger.log("Matched: " + owner + "/" + loc + " -> Zeile " + row);
      } else {
        Logger.log("KEIN MATCH: " + owner + " / " + loc);
      }
    });
  }

  // Schmuck-Preis -> M5
  if (schmuckPreis) {
    sheet.getRange(5, COL_SCHMUCK + 1).setValue(parseInt(schmuckPreis) || 0);
  }
}

function schreibeHousesRaw(haeuser, schliessfach, ts) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_HOUSES_RAW);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_HOUSES_RAW);
    sheet.appendRow(["zeitstempel","typ","ort","belegung","max","besitzer","gegenstand","anzahl"]);
  }
  if (sheet.getLastRow() > 1) sheet.deleteRows(2, sheet.getLastRow() - 1);

  const rows = [];
  (haeuser||[]).forEach(function(h) {
    if (!h.items || !h.items.length) {
      rows.push([ts,"Haus",h.location,h.current,h.max,h.owner,"(leer)",0]);
    } else {
      h.items.forEach(function(i) { rows.push([ts,"Haus",h.location,h.current,h.max,h.owner,i.name,i.amount]); });
    }
  });
  (schliessfach||[]).forEach(function(f) {
    if (!f.items || !f.items.length) {
      rows.push([ts,"SF",f.type,f.current,f.max,"-","(leer)",0]);
    } else {
      f.items.forEach(function(i) { rows.push([ts,"SF",f.type,f.current,f.max,"-",i.name,i.amount]); });
    }
  });
  if (rows.length) sheet.getRange(sheet.getLastRow()+1,1,rows.length,8).setValues(rows);
}

function schreibeSchmuckPreisLive(preis, ts) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_PREIS_LIVE);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_PREIS_LIVE);
    sheet.appendRow(["Zeitstempel","Preis (EUR)"]);
    sheet.setFrozenRows(1);
  }
  if (preis) sheet.appendRow([ts, parseInt(preis)||0]);
}

function schreibeLog(status, ts, details) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_LOG);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_LOG);
    sheet.appendRow(["Zeitstempel","Status","Details"]);
  }
  sheet.appendRow([ts, status, details]);
  if (sheet.getLastRow() > 501) sheet.deleteRows(2, sheet.getLastRow()-501);
}

function eingabeFormularAbschicken() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const eingabeWS = ss.getSheetByName("Beta Test Dima");
  let jWS = ss.getSheetByName("Test Eingabe");
  if (!jWS) { jWS = ss.insertSheet("Test Eingabe"); jWS.appendRow(["Resource","Stueckzahl"]); }
  const werte = ["V40","V42"].map(f => eingabeWS.getRange(f).getValue());
  jWS.appendRow(werte);
}
