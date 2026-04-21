# apps/student/tests/test_views.py
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def student(db):
    return User.objects.create_user(
        email="sarah@test.com",
        password="testpass123",
        is_staff=False,
    )


@pytest.fixture
def instructor(db):
    return User.objects.create_user(
        email="prof@test.com",
        password="testpass123",
        is_staff=True,
    )


def test_login_get_returns_200(client):
    url = reverse("student:login")
    response = client.get(url)
    assert response.status_code == 200


def test_login_post_valid_redirects_to_home(client, student):
    url = reverse("student:login")
    response = client.post(url, {"email": "sarah@test.com", "password": "testpass123"})
    assert response.status_code == 302
    assert response["Location"] == reverse("student:home")


def test_login_post_invalid_rerenders_form(client, db):
    url = reverse("student:login")
    response = client.post(url, {"email": "nobody@test.com", "password": "wrong"})
    assert response.status_code == 200
    assert b"form" in response.content.lower()


def test_home_redirects_unauthenticated_to_student_login(client):
    url = reverse("student:home")
    response = client.get(url)
    assert response.status_code == 302
    assert "/s/login/" in response["Location"]


def test_home_redirects_instructor_to_dashboard(client, instructor):
    client.force_login(instructor)
    url = reverse("student:home")
    response = client.get(url)
    assert response.status_code == 302
    assert "/dashboard/" in response["Location"]

def test_home_returns_200_for_student(client, student):
    client.force_login(student)
    url = reverse("student:home")
    response = client.get(url)
    assert response.status_code == 200


def test_home_context_has_units(client, student):
    client.force_login(student)
    url = reverse("student:home")
    response = client.get(url)
    assert "units" in response.context
    assert len(response.context["units"]) >= 1


def test_home_context_has_resume_url_when_in_progress(client, student, db):
    client.force_login(student)
    url = reverse("student:home")
    response = client.get(url)
    assert "resume_url" in response.context  # may be None if no playlists

def test_unit_view_returns_200_for_student(client, student):
    client.force_login(student)
    url = reverse("student:unit", kwargs={"unit_num": 1})
    response = client.get(url)
    assert response.status_code == 200


def test_unit_view_context_has_skills(client, student):
    client.force_login(student)
    url = reverse("student:unit", kwargs={"unit_num": 1})
    response = client.get(url)
    assert "skills" in response.context
    assert len(response.context["skills"]) >= 1

def test_player_view_404_without_playlist_param(client, student):
    client.force_login(student)
    url = reverse("student:player", kwargs={"unit_num": 1})
    response = client.get(url)
    assert response.status_code == 404


def test_player_view_404_with_bad_playlist_id(client, student):
    client.force_login(student)
    url = reverse("student:player", kwargs={"unit_num": 1}) + "?playlist=NONEXISTENT"
    response = client.get(url)
    assert response.status_code == 404


def test_player_view_200_with_valid_playlist(client, student, db):
    from apps.exercises.models import Playlist, Exercise
    ex = Exercise(data={"chord":[]}, authored_by=student)
    ex.save()
    playlist = Playlist(name="Test Playlist", tags=["unit:1", "Note_Names"], authored_by=student)
    playlist.save()
    playlist.exercises.add(ex, through_defaults={"order": 1})
    
    client.force_login(student)
    url = reverse("student:player", kwargs={"unit_num": 1}) + f"?playlist={playlist.id}"
    response = client.get(url)
    assert response.status_code == 200


