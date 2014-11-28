define(["backbone"], function(Backbone) {
  /**
   * Simple model for an asset.
   */
  var Video = Backbone.Model.extend({
    defaults: {
      display_name: "",
      date_added: "",
      url: "",
      external_url: "",
      portable_url: "",
    }
  });
  return Video;
});
