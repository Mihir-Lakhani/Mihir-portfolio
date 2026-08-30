import unittest
from uuid import uuid4

from rag.session_memory import InMemoryConversationSessionStore, parse_browser_session_id


class ConversationSessionMemoryTests(unittest.TestCase):
    def test_browser_session_id_must_be_a_uuid(self):
        session_id = str(uuid4())

        self.assertEqual(parse_browser_session_id(session_id), session_id)
        self.assertIsNone(parse_browser_session_id("not-a-browser-session"))
        self.assertIsNone(parse_browser_session_id(None))

    def test_store_refreshes_active_session_and_drops_expired_state(self):
        store = InMemoryConversationSessionStore()
        session_id = str(uuid4())
        store.save(session_id, "interaction-one", ttl_seconds=10, now=100.0)

        self.assertEqual(
            store.previous_interaction_id(session_id, ttl_seconds=10, now=105.0),
            "interaction-one",
        )
        self.assertEqual(
            store.previous_interaction_id(session_id, ttl_seconds=10, now=114.9),
            "interaction-one",
        )
        self.assertIsNone(
            store.previous_interaction_id(session_id, ttl_seconds=10, now=125.0)
        )

    def test_store_keeps_only_a_short_navigation_category_without_chat_text(self):
        store = InMemoryConversationSessionStore()
        session_id = str(uuid4())

        store.save(
            session_id,
            "interaction-one",
            ttl_seconds=60,
            now=100.0,
            navigation_topic="profile",
        )

        self.assertEqual(store.navigation_topic(session_id, ttl_seconds=60, now=101.0), "profile")
        self.assertNotIn("Tell me", repr(store._sessions[session_id]))

    def test_pop_removes_the_only_provider_identifier(self):
        store = InMemoryConversationSessionStore()
        session_id = str(uuid4())
        store.save(session_id, "interaction-one", ttl_seconds=60, now=100.0)

        self.assertEqual(store.pop(session_id, now=101.0), "interaction-one")
        self.assertIsNone(store.previous_interaction_id(session_id, ttl_seconds=60, now=102.0))


if __name__ == "__main__":
    unittest.main()
