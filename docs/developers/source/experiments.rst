*******************************************
Content experiments
*******************************************

This is a brief overview of the support for content experiments in the platform.

For now, there is only one type of experiment: content split testing.  This lets course authors define an experiment with several *experimental conditions*, add xblocks that reference that experiment in various places in the course, and specify what content students in each experimental condition should see.  The LMS provides a way to randomly assign students to experimental conditions for each experiment, so that they see the right content at runtime.

Experimental conditions are essentially just a set of groups to put users into.  This applies to other non-experiment uses, so the implementation is done via a generic UserSegmentation interface.  Copying the doc string, a UserSegmentation is:

    A named way to segment users into groups, for any number of reasons.

    A segmentation may completely partition students in some group
    (e.g. everyone enrolled in a course), with each student in exactly one
    group, but it doesn't have to.  Some students may not be in any group in a
    segmentation, and some may be in multiple groups.

    There can be many types of segmentations, and some segmentations may have
    further invariants.  e.g. segmentations used for split testing will probably
    be partititions of students within a course, with each student being in
    exactly one group for an experiment.

    A Segmentation has an id, type, name, description, and a list of groups.
    The id is intended to be unique within a per-type context (e.g. for
    segmentations of users within a course, the ids should be unique per-course)

    Currently known segmentation types:
    'experiment': a segmentation used for testing of content.
        Intended for partitioning users in a course into non-overlapping groups.

The LMS has an app for managing UserSegmentation state: course_user_segmentation.  It provides an interface to store and retrieve the groups a user is in for particular segmentations.

The course_user_segmentation app is used by the LMS experiment app, which understands the particular semantics of experiments (e.g. the fact that the segmentation of users for an experiment must be a complete partition, with users assigned into exactly one group).

User metadata service
---------------------

Goals: provide a standard way to store information about users, to be used e.g. by XBlocks.  Make it easily in analytics.

- allow per-user key/value stores.
- keys can be per-course, or global

XBlock integration:
- the LMS runtime will provide a convenient way for XBlocks to get/set per-user tags.
   - it will internally munge the keys to 
- Q: can an XBlock set global user state (e.g. not per-course)?
- Q: can an XBlock read global user state
- Q: can an XBlock read tags set by other XBlocks?  (yes)
- Q: can an XBlock write tags set by other XBlocks? 
    

Questions:
- How to avoid name collisions in the keys?  A: some convention. e.g. for xblocks: "{xblock_type}.{key_name}"
- How to know types of values?  A: Victims, er... users have to know what they're getting
- Cale already said yes, but do we really really want to dump all the user's tag in every event?


``runtime.user_info.get(<SCOPE>, key)``
``runtime.user_info.set(<SCOPE>, key, value)``

``SCOPE = {this_xblock_course, this_xblock_global, global_course, global_global}  (need better names :)``

Alternative, could rely on convention for non-collision between xblocks:

``key = "my_xblock_type." + "actual_key_name"``
``runtime.user_info.set(SCOPE, key, value)``

``SCOPE = {GLOBAL, COURSE}``




Assumptions:
----------------

- UserSegmentations, at least of type 'experiment' are configured 

Questions:
----------------

- Is a generic UserSegmentation model useful enough to make up for the extra complexity of manually managing added invariants that a dedicated ExperimentsGroups abstraction could enforce?  The benefit is that we are going to have lots of uses for groups, and this makes it easier to have them work together.  e.g.:
   - "I want to do an AB test of video vs text explanations, and later I want to further split the A and B groups and conditionally show people in those groups different questions, based on whether or not they got a certain grade on PS3 (i.e. not randomly)..."
   - "I want to upload a csv that splits users into groups, and use that as the basis for conditional assignment later".
   - "I want the way we divide users into small discussion groups to be based on what A/B test group they are in"

- Technical: the implementation of user groups uses the UserSegmentation API roughly like this (experiment.py): 
   1. Is user in a group?
   2. If not, put them in a randomly chosen one.
  Without transactions, this definitely has a race condition where the user can end up in two groups.  With full locking of the table around both steps, it would be fine.  I'm not sure what our current transaction behavior is.

- XBlock--there doesn't seem to be a generic way for the split_test_module XBlock to get at the course it's a child of, and thus no good way to get at ``course.user_segmentation_list`` e.g. for displaying of the config to staff.  One option is to make a new scope (per-course, per-block-type), and duplicate the info there.  The current generic ``UserSegmentation`` abstraction seems nicer per the comments above.  (see TODO comments in ``split_test_module.py``)

- analysis -- the UserSegmentation table is 


Where the code is:
----------------


common:

- split_test_module -- a block that has one child per experimental condition (could be a vertical or other container with more blocks inside), and config specifying which child corresponds to which condition.
- course_module -- a course has a list of UserSegmentations, each of which specifies the number 

LMS:

- runtime--LmsExperimentSupport mixin.  Provides a way for split_test_modules to get the experimental condition for a user in the lms.
-  experiment djangoapp--provides a simple service-like API for the above.  Does the random assignment of studens to experimental conditions, and persists the results.

Things to watch out for (some not implemented yet):

- grade export needs to be smarter, because different students can see different graded things
- grading needs to only grade the children that a particular student sees (so if there are problems in both conditions in a split_test, any student would see only one set)
- ui -- icons in sequences need to be passed through
   - tooltips need to be passed through
- author changes post-release: conditions can be added or deleted after an experiment is live.  This is usually a bad idea, but can be useful, so it's allowed.  Need to handle all the cases.
- analytics logging around this is important.  
 
