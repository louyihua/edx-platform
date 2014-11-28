define(["js/views/baseview", "underscore", "gettext", "js/views/feedback_prompt", "js/views/feedback_notification"],
    function(BaseView, _, gettext, PromptView, NotificationView) {
var VideoView = BaseView.extend({
  initialize: function() {
    this.template = this.loadTemplate("video");
  },
  tagName: "tr",
  events: {
    "click .remove-video-button": "confirmDelete",
  },

  render: function() {
    this.$el.html(this.template({
      display_name: this.model.get('display_name'),
      date_added: this.model.get('date_added'),
      url: this.model.get('url'),
      external_url: this.model.get('external_url'),
      portable_url: this.model.get('portable_url'),
    }));
    return this;
  },

  confirmDelete: function(e) {
    if(e && e.preventDefault) { e.preventDefault(); }
    var video = this.model, collection = this.model.collection;
    new PromptView.Warning({
      title: gettext("Delete Video Confirmation"),
      message: gettext("Are you sure you wish to delete this video. It cannot be reversed!\n\nAlso any content that links/refers to this video will no longer work"),
      actions: {
        primary: {
          text: gettext("Delete"),
          click: function (view) {
            view.hide();
            video.destroy({
                wait: true, // Don't remove the asset from the collection until successful.
                success: function () {
                  new NotificationView.Confirmation({
                    title: gettext("Your video has been deleted."),
                    closeIcon: false,
                    maxShown: 2000
                  }).show();
                }
            });
          }
        },
        secondary: {
          text: gettext("Cancel"),
          click: function (view) {
            view.hide();
          }
        }
      }
    }).show();
  },
});

return VideoView;
}); // end define()
