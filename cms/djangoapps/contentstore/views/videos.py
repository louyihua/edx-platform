import logging
from functools import partial
import math
import json
import os
from datetime import datetime

from django.core.cache import cache
from django.http import HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django_future.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.conf import settings

from edxmako.shortcuts import render_to_response

from contentstore.utils import reverse_course_url
from xmodule.modulestore.django import modulestore
from xmodule.exceptions import NotFoundError
from django.core.exceptions import PermissionDenied
from opaque_keys.edx.keys import CourseKey

from util.date_utils import get_default_time_display
from util.json_request import JsonResponse
from django.http import HttpResponseNotFound
from django.utils.translation import ugettext as _
from .access import has_course_access
from xmodule.modulestore.exceptions import ItemNotFoundError

__all__ = ['videos_handler']
VIDEO_URL_BASE = '/media'
VIDEO_PATH_BASE = '/edx/var/edxapp'


# pylint: disable=unused-argument
@login_required
@ensure_csrf_cookie
def videos_handler(request, course_key_string=None, asset_key_string=None):
    """
    The restful handler for videos.
    It allows retrieval of all the videos (as an HTML page), as well as uploading new videos,
    deleting videos, and changing the "locked" state of an video.

    GET
        html: return an html page which will show all course videos. Note that only the video container
            is returned and that the actual videos are filled in with a client-side request.
        json: returns a page of videos. The following parameters are supported:
            page: the desired page of results (defaults to 0)
            page_size: the number of items per page (defaults to 50)
            sort: the video field to sort by (defaults to "date_added")
            direction: the sort direction (defaults to "descending")
    POST
        json: create (or update?) an video. The only updating that can be done is changing the lock state.
    PUT
        json: update the locked state of an video
    DELETE
        json: delete an video
    """
    course_key = CourseKey.from_string(course_key_string)
    if not has_course_access(request.user, course_key):
        raise PermissionDenied()

    response_format = request.REQUEST.get('format', 'html')
    if response_format == 'json' or 'application/json' in request.META.get('HTTP_ACCEPT', 'application/json'):
        if request.method == 'GET':
            return _videos_json(request, course_key)
        else:
            video_key = asset_key_string[4:] if asset_key_string else None
            return _update_video(request, course_key, video_key)
    elif request.method == 'GET':  # assume html
        return _video_index(request, course_key)
    else:
        return HttpResponseNotFound()


def _video_index(request, course_key):
    """
    Display an editable asset library.

    Supports start (0-based index into the list of assets) and max query parameters.
    """
    course_module = modulestore().get_course(course_key)

    return render_to_response('video_index.html', {
        'context_course': course_module,
        'video_callback_url': reverse_course_url('videos_handler', course_key)
    })


def _videos_json(request, course_key):
    """
    Display an editable video library.

    Supports start (0-based index into the list of videos) and max query parameters.
    """
    requested_page = int(request.REQUEST.get('page', 0))
    requested_page_size = int(request.REQUEST.get('page_size', 50))
    requested_sort = request.REQUEST.get('sort', 'date_added')
    sort_ascending = False
    if request.REQUEST.get('direction', '').lower() == 'asc':
        sort_ascending = True

    current_page = max(requested_page, 0)
    start = current_page * requested_page_size
    videos, total_count = _get_videos_for_page(request, course_key, current_page, requested_page_size, requested_sort, sort_ascending)
    end = start + len(videos)

    # If the query is beyond the final page, then re-query the final page so that at least one asset is returned
    if requested_page > 0 and start >= total_count:
        current_page = int(math.floor((total_count - 1) / requested_page_size))
        start = current_page * requested_page_size
        videos, total_count = _get_videos_for_page(request, course_key, current_page, requested_page_size, requested_sort, sort_ascending)
        end = start + len(videos)

    return JsonResponse({
        'start': start,
        'end': end,
        'page': current_page,
        'pageSize': requested_page_size,
        'totalCount': total_count,
        'videos': videos,
        'sort': requested_sort,
    })


def _get_videos_for_page(request, course_key, current_page, page_size, sort, ascending):
    """
    Returns the list of assets for the specified page and page size.
    """
    start = current_page * page_size
    cache_name = 'videos:' + course_key.to_deprecated_string()
    url_path = _add_slash(course_key.to_deprecated_string())
    video_files = []
    if cache.get(cache_name) is None:
       for root, dirs, files in os.walk(VIDEO_PATH_BASE + VIDEO_URL_BASE + url_path):
           for name in files:
               file_path = os.path.join(root, name)
               date = datetime.utcfromtimestamp(os.stat(file_path).st_mtime)
               video_files.append(_get_video_json(name, date, url_path + '/' + name))
       cache.set(cache_name, video_files)
    else:
       video_files = cache.get(cache_name)

    return [sorted(video_files, lambda a, b: cmp(a[sort], b[sort]) if ascending else cmp(b[sort], a[sort]))[start : start + page_size], len(video_files)]


@require_POST
@ensure_csrf_cookie
@login_required
def _upload_video(request, course_key):
    '''
    This method allows for POST uploading of files into the course video
    library, which will be supported by file system.
    '''
    # Does the course actually exist?!? Get anything from it to prove its
    # existence
    try:
        modulestore().get_course(course_key)
    except ItemNotFoundError:
        # no return it as a Bad Request response
        logging.error("Could not find course: %s", course_key)
        return HttpResponseBadRequest()

    # compute a 'filename' which is similar to the location formatting, we're
    # using the 'filename' nomenclature since we're using a FileSystem paradigm
    # here. We're just imposing the Location string formatting expectations to
    # keep things a bit more consistent
    upload_file = request.FILES['file']
    file_name = upload_file.name.replace('/', '_')
    path_name = _add_slash(course_key.to_deprecated_string())

    content_loc = path_name + '/' + file_name
    file_path = VIDEO_PATH_BASE + VIDEO_URL_BASE + content_loc
    dir_path = VIDEO_PATH_BASE + VIDEO_URL_BASE + path_name

    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    with open(file_path, "wb+") as fp:
        if upload_file.multiple_chunks():
            for chunk in upload_file.chunks():
                fp.write(chunk)
        else:
            fp.write(upload_file.read())

    cache.delete('videos:' + course_key.to_deprecated_string())

    response_payload = {
        'video': _get_video_json(upload_file.name, datetime.utcfromtimestamp(os.stat(file_path).st_mtime), content_loc),
        'msg': _('Upload completed')
    }

    return JsonResponse(response_payload)


@require_http_methods(("DELETE", "POST", "PUT"))
@login_required
@ensure_csrf_cookie
def _update_video(request, course_key, video_key):
    """
    restful CRUD operations for a course video.
    Currently only DELETE, POST, and PUT methods are implemented.

    asset_path_encoding: the odd /c4x/org/course/category/name repr of the video (used by Backbone as the id)
    """
    if request.method == 'DELETE':
        # Make sure the item to delete actually exists.
        try:
            file_path = VIDEO_PATH_BASE + VIDEO_URL_BASE + _add_slash(video_key)
        except:
            return HttpResponseBadRequest()
        if os.path.exists(file_path):
            os.remove(file_path)
            cache.delete('videos:' + course_key.to_deprecated_string())
            return JsonResponse()
        else:
            return JsonResponse(status=404)

    elif request.method in ('PUT', 'POST'):
        if 'file' in request.FILES:
            return _upload_video(request, course_key)
        else:
            # Update existing video
            try:
                modified_video = json.loads(request.body)
            except ValueError:
                return HttpResponseBadRequest()
            return JsonResponse(modified_video, status=201)


def _get_video_json(display_name, date, location):
    """
    Helper method for formatting the video information to send to client.
    """
    video_url = VIDEO_URL_BASE + _add_slash(location)
    external_url = settings.LMS_BASE + video_url
    return {
        'display_name': display_name,
        'date_added': get_default_time_display(date),
        'url': video_url,
        'external_url': external_url,
        'portable_url': video_url,
        'id': unicode("/c4x" + _add_slash(location))
    }


def _add_slash(url):
    if not url.startswith('/'):
        url = '/' + url  # TODO - re-address this once LMS-11198 is tackled.
    return url
