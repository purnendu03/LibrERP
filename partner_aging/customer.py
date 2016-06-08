# -*- coding: utf-8 -*-

######################################################################
#
#  Note: Program metadata is available in /__init__.py
#
######################################################################
from openerp.tools.translate import _
from openerp.osv import orm, fields
import tools


class account_aging_customer(orm.Model):
    _name = 'partner.aging.customer'
    _auto = False

    def docopen(self, cr, uid, ids, context=None):
        """
        @description  Open document (invoice or payment) related to the
                      unapplied payment or outstanding balance on this line
        """

        if not context:
            context = {}
        active_id = context.get('active_id')
        models = self.pool['ir.model.data']
        # Get this line's invoice id
        inv_id = self.browse(cr, uid, ids[0], context).invoice_id.id

        # if this is an unapplied payment(all unapplied payments hard-coded to -999),
        # get the referenced voucher
        if inv_id == -999:
            ref = self.browse(cr, uid, ids[0], context).invoice_ref
            payment_pool = self.pool['account.voucher']
            # Get referenced customer payment (invoice_ref field is actually a payment for these)
            voucher_id = payment_pool.search(cr, uid, [('number', '=', ref)], context=context)[0]
            view = models.get_object_reference(cr, uid, 'account_voucher', 'view_voucher_form')
            # Set values for form
            view_id = view and view[1] or False
            name = _('Customer Payments')
            res_model = 'account.voucher'
            ctx = "{}"
            doc_id = voucher_id
        # otherwise get the invoice
        else:
            view = models.get_object_reference(cr, uid, 'account', 'invoice_form')
            view_id = view and view[1] or False
            name = _('Customer Invoices')
            res_model = 'account.invoice'
            ctx = "{'type':'out_invoice'}"
            doc_id = inv_id

        if not doc_id:
            return {}

        # Open up the document's form
        return {
            'name': name,
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [view_id],
            'res_model': res_model,
            'context': ctx,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'res_id': doc_id,
        }

    _columns = {
        'partner_id': fields.many2one('res.partner', u'Partner', readonly=True),
        'partner_name': fields.text('Name', readonly=True),
        'avg_days_overdue': fields.integer(u'Avg Days Overdue', readonly=True),
        'date': fields.date(u'Due Date', readonly=True),
        'total': fields.float(u'Total', readonly=True),
        'days_due_01to30': fields.float(u'01/30', readonly=True),
        'days_due_31to60': fields.float(u'31/60', readonly=True),
        'days_due_61to90': fields.float(u'61/90', readonly=True),
        'days_due_91to120': fields.float(u'91/120', readonly=True),
        'days_due_121togr': fields.float(u'+121', readonly=True),
        'max_days_overdue': fields.integer(u'Days Overdue', readonly=True),
        'current': fields.float(u'Total', readonly=True),
        'invoice_ref': fields.char('Reference', size=25, readonly=True),
        'invoice_id': fields.many2one('account.invoice', 'Invoice', readonly=True),
        'comment': fields.text('Notes', readonly=True),
        'salesman': fields.many2one('res.users', u'Sales Rep', readonly=True),
    }

    _order = 'partner_name'

    def init(self, cr):
        """
        @author       Ursa Information Systems
        @description  Update table on load with latest aging information
        """

        query = """
                select id, partner_id, partner_name,salesman, avg_days_overdue, oldest_invoice_date as date, total, days_due_01to30,
                       days_due_31to60, days_due_61to90, days_due_91to120, days_due_121togr, max_days_overdue, current, invoice_ref, invoice_id, comment 
                       from account_voucher_customer_unapplied UNION
                SELECT * from (
                SELECT l.id as id,l.partner_id as partner_id, res_partner.name as "partner_name",
                    res_partner.user_id as salesman, days_due as "avg_days_overdue",
		    CASE WHEN ai.id is not null THEN ai.date_due ElSE l.date_maturity END as "date",
                    CASE WHEN ai.id is not null THEN 
                             CASE WHEN ai.type = 'out_refund' THEN -1*ai.residual ELSE ai.residual END 
                         WHEN ai.id is null THEN l.debit-l.credit ELSE 0 END as "total",
                    CASE WHEN (days_due BETWEEN 01 AND  30) and ai.id is not null THEN 
                             CASE WHEN ai.type = 'out_refund' then -1*ai.residual ELSE ai.residual END 
                         WHEN (days_due BETWEEN 01 and 30) and ai.id is null THEN l.debit - l.credit 
                         ELSE 0 END  AS "days_due_01to30",
                    CASE WHEN (days_due BETWEEN 31 AND  60) and ai.id is not null THEN
                             CASE WHEN ai.type = 'out_refund' THEN -1*ai.residual ELSE ai.residual END 
                         WHEN (days_due BETWEEN 31 and 60) and ai.id is null THEN l.debit - l.credit 
                         ELSE 0 END  AS "days_due_31to60",
                    CASE WHEN (days_due BETWEEN 61 AND  90) and ai.id is not null THEN 
                             CASE WHEN ai.type = 'out_refund' THEN -1*ai.residual ELSE ai.residual END 
                         WHEN (days_due BETWEEN 61 and 90) and ai.id is null THEN l.debit - l.credit 
                         ELSE 0 END  AS "days_due_61to90",
                    CASE WHEN (days_due BETWEEN 91 AND 120) and ai.id is not null THEN 
                             CASE WHEN ai.type = 'out_refund' THEN -1*ai.residual ELSE ai.residual END 
                         WHEN (days_due BETWEEN 91 and 120) and ai.id is null THEN l.debit - l.credit 
                         ELSE 0 END  AS "days_due_91to120",
                    CASE WHEN days_due >=121 and ai.id is not null THEN 
                             CASE WHEN ai.type = 'out_refund' THEN -1*ai.residual ELSE ai.residual END 
                         WHEN days_due >=121 and ai.id is null THEN l.debit-l.credit 
                         ELSE 0 END AS "days_due_121togr",
                    CASE when days_due < 0 THEN 0 ELSE days_due END as "max_days_overdue",
                    CASE when days_due <= 0 and ai.id is not null THEN 
                             CASE WHEN ai.type = 'out_refund' THEN -1*ai.residual ELSE ai.residual END 
                         WHEN days_due <=0 and ai.id is null then l.debit-l.credit 
                         ELSE 0 END as "current",
                    ai.number as "invoice_ref",
                    ai.id as "invoice_id", ai.comment

                    FROM account_move_line as l
                INNER JOIN
                (
                   SELECT lt.id,
                   CASE WHEN inv.id is not null THEN EXTRACT(DAY FROM (now() - inv.date_due))
                   ELSE EXTRACT(DAY FROM (now() - lt.date_maturity)) END AS days_due
                   FROM account_move_line lt LEFT JOIN account_invoice inv on lt.move_id = inv.move_id 
                ) DaysDue
                ON DaysDue.id = l.id

                INNER JOIN account_account
                   ON account_account.id = l.account_id
                INNER JOIN res_company
                   ON account_account.company_id = res_company.id
                INNER JOIN account_move
                   ON account_move.id = l.move_id
                LEFT JOIN account_invoice as ai
                   ON ai.move_id = l.move_id
                INNER JOIN res_partner
                   ON res_partner.id = l.partner_id
                WHERE account_account.active
                  AND ai.state <> 'paid'
                  AND (account_account.type IN ('receivable'))
                  AND (l.reconcile_id IS NULL)
                  AND account_move.state = 'posted'
                  AND DaysDue.days_due is not null
                ) sq
              """

        tools.drop_view_if_exists(cr, '%s' % (self._name.replace('.', '_')))
        cr.execute("""
                      CREATE OR REPLACE VIEW %s AS ( %s)
        """ % (self._name.replace('.', '_'), query))
