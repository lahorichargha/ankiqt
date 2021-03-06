# Copyright: Damien Elmes <anki@ichi2.net>
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from aqt.qt import *
import aqt, simplejson
from anki.utils import ids2str
from aqt.utils import showInfo, showWarning, openHelp, getOnlyText
from operator import itemgetter

class DeckConf(QDialog):
    def __init__(self, mw):
        QDialog.__init__(self, mw)
        self.mw = mw
        self.deck = self.mw.col.decks.current()
        self.form = aqt.forms.dconf.Ui_Dialog()
        self.form.setupUi(self)
        self.mw.checkpoint(_("Options"))
        self.setupCombos()
        self.setupConfs()
        self.setWindowModality(Qt.WindowModal)
        self.connect(self.form.buttonBox,
                     SIGNAL("helpRequested()"),
                     lambda: openHelp("StudyOptions"))
        self.connect(self.form.confOpts, SIGNAL("clicked()"), self.confOpts)
        self.form.confOpts.setText(u"▾")
        self.connect(self.form.buttonBox.button(QDialogButtonBox.RestoreDefaults),
                     SIGNAL("clicked()"),
                     self.onRestore)
        self.setWindowTitle(_("Options for %s") % self.deck['name'])
        self.exec_()

    def setupCombos(self):
        import anki.consts as cs
        f = self.form
        f.newOrder.addItems(cs.newCardOrderLabels().values())
        f.revOrder.addItems(cs.revCardOrderLabels().values())
        self.connect(f.newOrder, SIGNAL("currentIndexChanged(int)"),
                     self.onNewOrderChanged)

    # Conf list
    ######################################################################

    def setupConfs(self):
        self.connect(self.form.dconf, SIGNAL("currentIndexChanged(int)"),
                     self.onConfChange)
        self.conf = None
        self.loadConfs()

    def loadConfs(self):
        current = self.deck['conf']
        self.confList = self.mw.col.decks.allConf()
        self.confList.sort(key=itemgetter('name'))
        startOn = None
        self.ignoreConfChange = True
        self.form.dconf.clear()
        for idx, conf in enumerate(self.confList):
            self.form.dconf.addItem(conf['name'])
            if conf['id'] == current:
                startOn = idx
        self.ignoreConfChange = False
        self.form.dconf.setCurrentIndex(startOn)
        self.onConfChange(startOn)

    def confOpts(self):
        m = QMenu(self.mw)
        a = m.addAction(_("Add"))
        a.connect(a, SIGNAL("triggered()"), self.addGroup)
        a = m.addAction(_("Delete"))
        a.connect(a, SIGNAL("triggered()"), self.remGroup)
        a = m.addAction(_("Rename"))
        a.connect(a, SIGNAL("triggered()"), self.renameGroup)
        m.exec_(QCursor.pos())

    def onConfChange(self, idx):
        if self.ignoreConfChange:
            return
        if self.conf:
            self.saveConf()
        conf = self.confList[idx]
        self.deck['conf'] = conf['id']
        self.loadConf()

    def addGroup(self):
        name = getOnlyText(_("New options group name:"))
        if not name:
            return
        # first, save currently entered data to current conf
        self.saveConf()
        # then clone the conf
        id = self.mw.col.decks.confId(name, cloneFrom=self.conf)
        # set the deck to the new conf
        self.deck['conf'] = id
        # then reload the conf list
        self.loadConfs()

    def remGroup(self):
        if self.conf['id'] == 1:
            showInfo(_("The default configuration can't be removed."), self)
        else:
            self.mw.col.decks.remConf(self.conf['id'])
            self.deck['conf'] = 1
            self.loadConfs()

    def renameGroup(self):
        name = getOnlyText(_("New name:"))
        if not name:
            return
        self.conf['name'] = name
        self.loadConfs()

    # Loading
    ##################################################

    def listToUser(self, l):
        return " ".join([str(x) for x in l])

    def loadConf(self):
        self.conf = self.mw.col.decks.confForDid(self.deck['id'])
        # new
        c = self.conf['new']
        f = self.form
        f.lrnSteps.setText(self.listToUser(c['delays']))
        f.lrnGradInt.setValue(c['ints'][0])
        f.lrnEasyInt.setValue(c['ints'][1])
        f.lrnFactor.setValue(c['initialFactor']/10.0)
        f.newOrder.setCurrentIndex(c['order'])
        f.newPerDay.setValue(c['perDay'])
        f.separate.setChecked(c['separate'])
        # rev
        c = self.conf['rev']
        f.revPerDay.setValue(c['perDay'])
        f.revOrder.setCurrentIndex(c['order'])
        f.revSpace.setValue(c['fuzz']*100)
        f.revMinSpace.setValue(c['minSpace'])
        f.easyBonus.setValue(c['ease4']*100)
        f.fi1.setValue(c['fi'][0])
        f.fi2.setValue(c['fi'][1])
        # lapse
        c = self.conf['lapse']
        f.lapSteps.setText(self.listToUser(c['delays']))
        f.lapMult.setValue(c['mult']*100)
        f.lapMinInt.setValue(c['minInt'])
        f.leechThreshold.setValue(c['leechFails'])
        f.leechAction.setCurrentIndex(c['leechAction'])
        # general
        c = self.conf
        f.maxTaken.setValue(c['maxTaken'])
        f.showTimer.setChecked(c.get('timer', 0))
        f.autoplaySounds.setChecked(c['autoplay'])
        # description
        f.desc.setPlainText(self.deck['desc'])

    def onRestore(self):
        self.mw.progress.start()
        self.mw.col.decks.restoreToDefault(self.conf)
        self.mw.progress.finish()
        self.loadConf()

    # New order
    ##################################################

    def onNewOrderChanged(self, new):
        old = self.conf['new']['order']
        if old == new:
            return
        self.conf['new']['order'] = new
        self.mw.progress.start()
        self.mw.col.sched.resortConf(self.conf)
        self.mw.progress.finish()

    # Saving
    ##################################################

    def updateList(self, conf, key, w, minSize=1):
        items = unicode(w.text()).split(" ")
        ret = []
        for i in items:
            if not i:
                continue
            try:
                i = float(i)
                assert i > 0
                if i == int(i):
                    i = int(i)
                ret.append(i)
            except:
                # invalid, don't update
                showWarning(_("Steps must be numbers."))
                return
        if len(ret) < minSize:
            showWarning(_("At least one step is required."))
            return
        conf[key] = ret

    def saveConf(self):
        # new
        c = self.conf['new']
        f = self.form
        self.updateList(c, 'delays', f.lrnSteps)
        c['ints'][0] = f.lrnGradInt.value()
        c['ints'][1] = f.lrnEasyInt.value()
        c['initialFactor'] = f.lrnFactor.value()*10
        c['order'] = f.newOrder.currentIndex()
        c['perDay'] = f.newPerDay.value()
        c['separate'] = f.separate.isChecked()
        # rev
        c = self.conf['rev']
        c['perDay'] = f.revPerDay.value()
        c['fuzz'] = f.revSpace.value()/100.0
        c['minSpace'] = f.revMinSpace.value()
        c['ease4'] = f.easyBonus.value()/100.0
        c['order'] = f.revOrder.currentIndex()
        c['fi'] = [f.fi1.value(), f.fi2.value()]
        # lapse
        c = self.conf['lapse']
        self.updateList(c, 'delays', f.lapSteps, minSize=0)
        c['mult'] = f.lapMult.value()/100.0
        c['minInt'] = f.lapMinInt.value()
        c['leechFails'] = f.leechThreshold.value()
        c['leechAction'] = f.leechAction.currentIndex()
        # general
        c = self.conf
        c['maxTaken'] = f.maxTaken.value()
        c['timer'] = f.showTimer.isChecked() and 1 or 0
        c['autoplay'] = f.autoplaySounds.isChecked()
        # description
        self.deck['desc'] = f.desc.toPlainText()
        self.mw.col.decks.save(self.conf)

    def reject(self):
        self.accept()

    def accept(self):
        self.saveConf()
        self.mw.reset()
        QDialog.accept(self)
