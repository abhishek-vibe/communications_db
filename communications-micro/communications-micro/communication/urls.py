from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router and register viewsets
router = DefaultRouter()
router.register(r'broadcasts', views.BroadcastViewSet, basename='broadcast')
router.register(r'events', views.EventViewSet, basename='event')
router.register(r'media', views.MediaViewSet, basename='media')
router.register(r'groups', views.GroupViewSet, basename='group')

app_name = 'communications'

urlpatterns = [
    # Include router URLs - this will create all the API endpoints  
    path('api/', include(router.urls)),
    # Remove the circular import line - DON'T include self!
    # path('communications/', include('communications.urls')),  # This causes circular import
]

# The router automatically generates these URLs:
# GET/POST     /api/broadcasts/                           - List/Create broadcasts
# GET/PUT/PATCH/DELETE /api/broadcasts/{id}/               - Retrieve/Update/Delete broadcast
# POST         /api/broadcasts/{id}/acknowledge/          - Acknowledge broadcast
# POST         /api/broadcasts/{id}/mark_viewed/          - Mark broadcast as viewed
# GET          /api/broadcasts/{id}/analytics/            - Get broadcast analytics
# GET          /api/broadcasts/my_broadcasts/             - Get user's broadcasts

# GET/POST     /api/events/                               - List/Create events
# GET/PUT/PATCH/DELETE /api/events/{id}/                  - Retrieve/Update/Delete event
# POST         /api/events/{id}/rsvp/                     - RSVP to event
# GET          /api/events/{id}/rsvp_list/                - Get RSVP list (admin only)
# GET          /api/events/{id}/analytics/                - Get event analytics
# GET          /api/events/my_events/                     - Get user's events
# GET          /api/events/upcoming/                      - Get upcoming events

# GET/POST     /api/media/                                - List/Upload media
# GET/PUT/PATCH/DELETE /api/media/{id}/                   - Retrieve/Update/Delete media
# GET          /api/media/my_uploads/                     - Get user's uploads

# GET/POST     /api/groups/                               - List/Create groups
# GET/PUT/PATCH/DELETE /api/groups/{id}/                  - Retrieve/Update/Delete group
# POST         /api/groups/{id}/join/                     - Join group
# POST         /api/groups/{id}/leave/                    - Leave group
# GET          /api/groups/my_groups/                     - Get user's groups