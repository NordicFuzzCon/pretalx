import pytest
from django.core import mail as djmail
from django.urls import reverse

from pretalx.event.models import TeamInvite


@pytest.mark.django_db
def test_orga_successful_login(client, user, template_patch):
    user.set_password('testtest')
    user.save()
    response = client.post(reverse('orga:login'), data={'email': user.email, 'password': 'testtest'}, follow=True)
    assert response.redirect_chain[-1][0] == '/orga/event/'
    assert response.status_code == 200


@pytest.mark.django_db
def test_orga_redirect_login(client, orga_user, event):
    queryparams = 'something=else&foo=bar'
    request_url = event.orga_urls.base + '/?' + queryparams
    response = client.get(request_url, follow=True)
    assert response.status_code == 200
    # query parameters need to be sorted because their order is not stable with Python 3.5
    queryparams_list = queryparams.split('&').sort()
    # get response redirect chain in a stable sorted order
    redir_chain_sorted_path_and_qs = response.redirect_chain[-1][0].split('?')
    redir_chain_sorted_path = redir_chain_sorted_path_and_qs[0]
    redir_chain_sorted_qs = redir_chain_sorted_path_and_qs[1].split('&').sort()
    # check path
    assert redir_chain_sorted_path == '/orga/login/'
    # check query string (as list and sorted)
    assert redir_chain_sorted_qs == queryparams_list
    # check status code
    assert response.redirect_chain[-1][1] == 302

    response = client.post(response.redirect_chain[-1][0], data={'email': orga_user.email, 'password': 'orgapassw0rd'}, follow=True)
    assert response.status_code == 200
    assert event.name in response.content.decode()


@pytest.mark.django_db
def test_orga_accept_invitation_once(client, event, invitation):
    team = invitation.team
    count = invitation.team.members.count()
    token = invitation.token
    response = client.post(
        reverse('orga:invitation.view', kwargs={'code': invitation.token}),
        {
            'register_email': invitation.email,
            'register_password': 'f00baar!',
            'register_password_repeat': 'f00baar!',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert team.members.count() == count + 1
    assert team.invites.count() == 0
    with pytest.raises(TeamInvite.DoesNotExist):
        invitation.refresh_from_db()
    response = client.get(
        reverse('orga:invitation.view', kwargs={'code': token}),
        follow=True
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_orga_registration_errors(client, event, invitation, user):
    team = invitation.team
    count = invitation.team.members.count()
    response = client.post(
        reverse('orga:invitation.view', kwargs={'code': invitation.token}),
        {
            'register_email': user.email,
            'register_password': 'f00baar!',
            'register_password_repeat': 'f00baar!',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert team.members.count() == count
    assert team.invites.count() == 1


@pytest.mark.django_db
def test_orga_registration_errors_weak_password(client, event, invitation, user):
    team = invitation.team
    count = invitation.team.members.count()
    response = client.post(
        reverse('orga:invitation.view', kwargs={'code': invitation.token}),
        {
            'register_email': user.email,
            'register_password': 'password',
            'register_password_repeat': 'password',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert team.members.count() == count
    assert team.invites.count() == 1


@pytest.mark.django_db
def test_orga_incorrect_invite_token(client, event, invitation):
    response = client.get(
        reverse('orga:invitation.view', kwargs={'code': invitation.token + 'WRONG'}),
        follow=True
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_can_reset_password_by_email(orga_user, client, event):
    djmail.outbox = []
    response = client.post(
        '/orga/reset/',
        data={'login_email': orga_user.email, },
        follow=True,
    )
    orga_user.refresh_from_db()
    reset_token = orga_user.pw_reset_token
    assert response.status_code == 200
    assert reset_token
    assert len(djmail.outbox) == 1

    # Make sure we can do this only once
    response = client.post(
        '/orga/reset/',
        data={'login_email': orga_user.email, },
        follow=True,
    )
    orga_user.refresh_from_db()
    assert response.status_code == 200
    assert orga_user.pw_reset_token
    assert orga_user.pw_reset_token == reset_token
    assert len(djmail.outbox) == 1

    response = client.post(
        '/orga/reset/{}'.format(orga_user.pw_reset_token),
        data={'password': 'mynewpassword1!', 'password_repeat': 'mynewpassword1!'},
        follow=True,
    )
    assert response.status_code == 200
    orga_user.refresh_from_db()
    assert not orga_user.pw_reset_token
    response = client.post(
        event.urls.login,
        data={'login_email': orga_user.email, 'login_password': 'mynewpassword1!'},
        follow=True,
    )
    assert 'You are logged in as' in response.content.decode()


@pytest.mark.django_db
def test_cannot_use_incorrect_token(orga_user, client, event):
    response = client.post(
        '/orga/reset/abcdefg',
        data={'password': 'mynewpassword1!', 'password_repeat': 'mynewpassword1!'},
        follow=True,
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_cannot_reset_password_with_incorrect_input(orga_user, client, event):
    response = client.post(
        '/orga/reset/',
        data={'login_email': orga_user.email, },
        follow=True,
    )
    assert response.status_code == 200
    orga_user.refresh_from_db()
    assert orga_user.pw_reset_token
    response = client.post(
        '/orga/reset/{}'.format(orga_user.pw_reset_token),
        data={'password': 'mynewpassword1!', 'password_repeat': 'mynewpassword123!'},
        follow=True,
    )
    assert response.status_code == 200
    orga_user.refresh_from_db()
    assert orga_user.pw_reset_token
    response = client.post(
        event.urls.login,
        data={'login_email': orga_user.email, 'login_password': 'mynewpassword1!'},
        follow=True,
    )
    assert 'You are logged in as' not in response.content.decode()


@pytest.mark.django_db
def test_cannot_reset_password_to_insecure_password(orga_user, client, event):
    response = client.post(
        '/orga/reset/',
        data={'login_email': orga_user.email, },
        follow=True,
    )
    assert response.status_code == 200
    orga_user.refresh_from_db()
    assert orga_user.pw_reset_token
    response = client.post(
        '/orga/reset/{}'.format(orga_user.pw_reset_token),
        data={'password': 'password', 'password_repeat': 'password'},
        follow=True,
    )
    assert response.status_code == 200
    orga_user.refresh_from_db()
    assert orga_user.pw_reset_token
    response = client.post(
        event.urls.login,
        data={'login_email': orga_user.email, 'login_password': 'password'},
        follow=True,
    )
    assert 'You are logged in as' not in response.content.decode()


@pytest.mark.django_db
def test_cannot_reset_password_without_account(orga_user, client, event):
    response = client.post(
        '/orga/reset/',
        data={'login_email': 'incorrect' + orga_user.email, },
        follow=True,
    )
    assert response.status_code == 200
