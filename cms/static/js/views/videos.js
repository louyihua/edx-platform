define(["jquery", "underscore", "gettext", "js/models/video", "js/views/paging", "js/views/video",
    "js/views/paging_header", "js/views/paging_footer", "js/utils/modal"],
    function($, _, gettext, VideoModel, PagingView, VideoView, PagingHeader, PagingFooter, ModalUtils) {

        var VideosView = PagingView.extend({
            // takes VideoCollection as model

            events : {
                "click .column-sort-link": "onToggleColumn",
                "click .upload-button": "showUploadModal"
            },

            initialize : function() {
                PagingView.prototype.initialize.call(this);
                var collection = this.collection;
                this.template = this.loadTemplate("video-library");
                this.listenTo(collection, 'destroy', this.handleDestroy);
                this.registerSortableColumn('js-video-name-col', gettext('Name'), 'display_name', 'asc');
                this.registerSortableColumn('js-video-date-col', gettext('Date Added'), 'date_added', 'desc');
                this.setInitialSortColumn('js-video-date-col');
                this.setPage(0);
                videosView = this;
            },

            render: function() {
                // Wait until the content is loaded the first time to render
                return this;
            },

            afterRender: function(){
                // Bind events with html elements
                $('li a.upload-button').on('click', this.showUploadModal);
                $('.upload-modal .close-button').on('click', this.hideModal);
                $('.upload-modal .choose-file-button').on('click', this.showFileSelectionMenu);
                return this;
            },

            getTableBody: function() {
                var tableBody = this.tableBody;
                if (!tableBody) {
                    // Create the table
                    this.$el.html(this.template());
                    tableBody = this.$('#video-table-body');
                    this.tableBody = tableBody;
                    this.pagingHeader = new PagingHeader({view: this, el: $('#video-paging-header')});
                    this.pagingFooter = new PagingFooter({view: this, el: $('#video-paging-footer')});
                    this.pagingHeader.render();
                    this.pagingFooter.render();

                    // Hide the contents until the collection has loaded the first time
                    this.$('.asset-library').hide();
                    this.$('.no-asset-content').hide();
                }
                return tableBody;
            },

            renderPageItems: function() {
                var self = this,
                videos = this.collection,
                hasVideos = videos.length > 0,
                tableBody = this.getTableBody();
                tableBody.empty();
                if (hasVideos) {
                    videos.each(
                        function(video) {
                            var view = new VideoView({model: video});
                            tableBody.append(view.render().el);
                        }
                    );
                }
                self.$('.asset-library').toggle(hasVideos);
                self.$('.no-asset-content').toggle(!hasVideos);
                return this;
            },

            onError: function() {
            },

            handleDestroy: function(model) {
                this.collection.fetch({reset: true}); // reload the collection to get a fresh page full of items
                analytics.track('Deleted Video', {
                    'course': course_location_analytics,
                    'id': model.get('url')
                });
            },

            addVideo: function (model) {
                // Switch the sort column back to the default (most recent date added) and show the first page
                // so that the new video is shown at the top of the page.
                this.setInitialSortColumn('js-video-date-col');
                this.setPage(0);

                analytics.track('Uploaded a File', {
                    'course': course_location_analytics,
                    'video_url': model.get('url')
                });
            },

            onToggleColumn: function(event) {
                var columnName = event.target.id;
                this.toggleSortOrder(columnName);
            },

            hideModal: function (event) {
                if (event) {
                    event.preventDefault();
                }
                $('.file-input').unbind('change.startUpload');
                ModalUtils.hideModal();
            },

            showUploadModal: function (event) {
                var self = videosView;
                event.preventDefault();
                self.resetUploadModal();
                ModalUtils.showModal();
                $('.file-input').bind('change', self.startUpload);
                $('.upload-modal .file-chooser').fileupload({
                    dataType: 'json',
                    type: 'POST',
                    maxChunkSize: 1024 * 1024 * 1024,      // 1 GB
                    autoUpload: true,
                    progressall: function(event, data) {
                        var percentComplete = parseInt((100 * data.loaded) / data.total, 10);
                        self.showUploadFeedback(event, percentComplete);
                    },
                    maxFileSize: 1024 * 1024 * 1024,   // 1 GB
                    maxNumberofFiles: 100,
                    add: function(event, data) {
                        data.process().done(function () {
                            data.submit();
                        });
                    },
                    done: function(event, data) {
                        self.displayFinishedUpload(data.result);
                    }

                });
            },

            showFileSelectionMenu: function(event) {
                event.preventDefault();
                $('.file-input').click();
            },

            startUpload: function (event) {
                var file = event.target.value;

                $('.upload-modal h1').text(gettext('Uploading…'));
                $('.upload-modal .file-name').html(file.substring(file.lastIndexOf("\\") + 1));
                $('.upload-modal .choose-file-button').hide();
                $('.upload-modal .progress-bar').removeClass('loaded').show();
            },

            resetUploadModal: function () {
                // Reset modal so it no longer displays information about previously
                // completed uploads.
                var percentVal = '0%';
                $('.upload-modal .progress-fill').width(percentVal);
                $('.upload-modal .progress-fill').html(percentVal);
                $('.upload-modal .progress-bar').hide();

                $('.upload-modal .file-name').show();
                $('.upload-modal .file-name').html('');
                $('.upload-modal .choose-file-button').text(gettext('Choose Video'));
                $('.upload-modal .embeddable-xml-input').val('');
                $('.upload-modal .embeddable').hide();
            },

            showUploadFeedback: function (event, percentComplete) {
                var percentVal = percentComplete + '%';
                $('.upload-modal .progress-fill').width(percentVal);
                $('.upload-modal .progress-fill').html(percentVal);
            },

            displayFinishedUpload: function (resp) {
                var video = resp.video;

                $('.upload-modal h1').text(gettext('Upload New Video'));
                $('.upload-modal .embeddable-xml-input').val(video.portable_url);
                $('.upload-modal .embeddable').show();
                $('.upload-modal .file-name').hide();
                $('.upload-modal .progress-fill').html(resp.msg);
                $('.upload-modal .choose-file-button').text(gettext('Load Another Video')).show();
                $('.upload-modal .progress-fill').width('100%');

                videosView.addVideo(new VideoModel(video));
            }
        });

        return VideosView;
    }); // end define();
