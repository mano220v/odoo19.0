# -*- coding: utf-8 -*-
from odoo import api, models


class GlobalSearchSpotlight(models.AbstractModel):
    """Backend engine for the Spotlight-style global search.

    This is an ``AbstractModel`` (no database table) rather than a
    controller: it is called directly from OWL via the ``orm`` service
    (``this.orm.call('global.search.spotlight', 'search_all', [query])``),
    which is the modern (17.0+) equivalent of a hand-rolled JSON-RPC
    controller and gets CSRF / session handling for free.

    SECURITY: we deliberately never call ``sudo()``. Every ``search()``
    call below runs in ``self.env`` - i.e. as the *currently logged in
    user* - so:
      * ``ir.model.access.csv`` (model-level CRUD rights) is enforced.
      * ``ir.rule`` (record rules, e.g. multi-company rules, sales team
        assignment rules, portal visibility rules, ...) is enforced.
    A user therefore can never see a result here that they could not
    already see by navigating to that model's own list view.
    """

    _name = 'global.search.spotlight'
    _description = 'Global Search Spotlight Engine'

    # Which models participate in the global search, and how to present
    # them. Extend this list (or override this method) to add more models,
    # e.g. ('project.task', 'Projects', 'fa-tasks').
    _SEARCHABLE_MODELS = [
        ('res.partner', 'Contacts', 'fa-address-book'),
        ('sale.order', 'Sales', 'fa-shopping-cart'),
        ('product.template', 'Products', 'fa-cube'),
    ]

    def _get_search_domain(self, model_name, query):
        """Return the search domain used for a given model.

        Kept as a separate, overridable method so downstream modules can
        extend/replace how a given model is matched (e.g. also match on
        VAT number for res.partner) without having to rewrite search_all().
        """
        if model_name == 'res.partner':
            return ['|', ('name', 'ilike', query), ('email', 'ilike', query)]
        if model_name == 'product.template':
            return ['|', ('name', 'ilike', query), ('default_code', 'ilike', query)]
        if model_name == 'sale.order':
            return ['|', ('name', 'ilike', query), ('partner_id.name', 'ilike', query)]
        return [('name', 'ilike', query)]

    @api.model
    def search_all(self, query, limit=5):
        """Search ``query`` across all configured models.

        :param str query: raw text typed by the user in the Spotlight input.
        :param int limit: max number of records returned *per model*.
        :return: list of dicts, e.g.
            [{'model': 'res.partner', 'id': 12, 'name': 'Azure Interior',
              'category': 'Contacts', 'icon': 'fa-address-book'}, ...]
        :rtype: list[dict]
        """
        query = (query or '').strip()
        if not query:
            return []

        results = []

        for model_name, category, icon in self._SEARCHABLE_MODELS:
            # Skip gracefully if the module providing this model isn't
            # installed on this database (e.g. 'sale.order' without Sales).
            if model_name not in self.env:
                continue

            Model = self.env[model_name]

            # Explicitly (and cheaply) verify read access before searching,
            # instead of letting an AccessError bubble up and abort the
            # *entire* global search just because the user lacks rights on
            # one of the several models we query.
            if not Model.check_access_rights('read', raise_exception=False):
                continue

            domain = self._get_search_domain(model_name, query)
            try:
                # search() itself re-applies ir.rule record rules for the
                # current user - this is where multi-company / sales-team /
                # portal restrictions are actually enforced.
                records = Model.search(domain, limit=limit)
            except Exception:
                # Defensive: never let one misbehaving model take down the
                # whole Spotlight search.
                continue

            for record in records:
                results.append({
                    'model': model_name,
                    'id': record.id,
                    'name': record.display_name or getattr(record, 'name', '') or '',
                    'category': category,
                    'icon': icon,
                })

        return results
