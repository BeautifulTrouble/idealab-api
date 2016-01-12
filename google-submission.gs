/* Submit to Beautiful Solutions lab on form submit */
 
function Initialize() {
 
  var triggers = ScriptApp.getProjectTriggers();
 
  for (var i in triggers) {
    ScriptApp.deleteTrigger(triggers[i]);
  }
 
  ScriptApp.newTrigger("SubmitToLab")
    .forSpreadsheet(SpreadsheetApp.getActiveSpreadsheet())
    .onFormSubmit()
    .create();
 
}
 
function SubmitToLab(e) {

  try {
    
    var field_mapping = {
      "name": /your name/i,
      "email": /email/i,
      "phone": /phone/i,
      "input": /input/i,
      "titles": /title\/name/i,
      "descriptions": /description/i,
      "links": /links/i,
      "authors": /author/i,
      "submit": /submit this/i,
    }
    var payload = {
      "secret": "REPLACE_WITH_SECRET_KEY",
      "publish": false
    }
    for (var questionName in e.namedValues) {
      for (var field in field_mapping) {
        if (field_mapping[field].test(questionName)) {
          payload[field] = e.namedValues[questionName];
        }
      }
    }
    
    var response = UrlFetchApp.fetch("https://solutions.thischangeseverything.org/api/ideas", {
      "method": "post",
      "payload": JSON.stringify(payload)
    });

    Logger.log(JSON.stringify(payload));    
    
  } catch (e) {
    Logger.log(e.toString());
  }

}
