'''
Created on Nov 11, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os, xml.dom.minidom, xml.parsers.expat
from collections import defaultdict
from arelle import (XbrlConst, XbrlUtil, XmlUtil, UrlUtil, ModelXbrl, ModelDocument, ModelObject, ModelVersObject)
from arelle.ModelValue import (qname, QName)

def create(modelXbrlFromDTS, modelXbrlToDTS):
    modelXbrlVersReport = ModelXbrl.create(modelXbrlFromDTS.modelManager)
    modelVersReport = ModelVersReport(
    	ModelDocument.Type.VERSIONINGREPORT)
    modelXbrlVersReport.modelDocument = modelVersReport
    modelVersReport.diffDTSes(modelXbrlFromDTS, modelXbrlToDTS)
    return modelVersReport

relationshipSetArcAttributesExclusion = {
    "{http://www.w3.org/1999/xlink}from",
    "{http://www.w3.org/1999/xlink}to",
    "{http://www.w3.org/1999/xlink}actuate",
    "{http://www.w3.org/1999/xlink}show",
    "{http://www.w3.org/1999/xlink}title",
    "{http://www.w3.org/XML/1998/namespace}lang", 
    "{http://www.w3.org/XML/1998/namespace}space",
    "id", "use","priority","order"
    }

class ModelVersReport(ModelDocument.ModelDocument):
    def __init__(self, modelXbrl, 
                 type=ModelDocument.Type.VERSIONINGREPORT, 
                 uri=None, filepath=None, xmlDocument=None):
        super().__init__(modelXbrl, type, uri, filepath, xmlDocument)
        self.fromDTS = None
        self.toDTS = None
        self.assignments = {}
        self.actions = {}
        self.namespaceRenameFrom = {}
        self.namespaceRenameTo = {}
        self.roleChangeFrom = {}
        self.roleChangeTo = {}
        self.roleChanges = {}
        self.conceptBasicChanges = []
        self.conceptExtendedChanges = []
        self.equivalentConcepts = {}
        self.relatedConcepts = defaultdict(set)
        self.relationshipSetChanges = []
        self.instanceAspectChanges = []
        self.typedDomainsCorrespond = {}
        
    def versioningReportDiscover(self, rootElement):
        actionRelatedFromMdlObjs = []
        actionRelatedToMdlObjs = []
        modelAction = None
        # add self to namespaced document
        self.xmlRootElement = rootElement
        try:
            for element in rootElement.getElementsByTagName("*"):
                ln = element.localName
                ns = element.namespaceURI
                tagName = element.tagName
                modelObject = None
                if ns == XbrlConst.ver:
                    if ln == "assignment":
                        modelObject = ModelVersObject.create(self, element)
                    elif ln == "action":
                        ModelVersObject.relateConceptMdlObjs(self, actionRelatedFromMdlObjs, actionRelatedToMdlObjs)
                        modelObject = ModelVersObject.create(self, element)
                        modelAction = modelObject
                        actionRelatedFromMdlObjs = []
                        actionRelatedToMdlObjs = []
                    elif (ln == "fromDTS" or ln == "toDTS") and not getattr(self, ln):
                        schemaRefElts = XmlUtil.children(element, XbrlConst.link, "schemaRef")
                        if schemaRefElts:
                            if len(schemaRefElts) == 1 and schemaRefElts[0].hasAttributeNS(XbrlConst.xlink, "href"):
                                DTSmodelXbrl = ModelXbrl.load(self.modelXbrl.modelManager,
                                      schemaRefElts[0].getAttributeNS(XbrlConst.xlink, "href"),
                                      "loading validation report", 
                                      base=self.baseForElement(schemaRefElts[0]))
                            else:   # need multi-schemaRefs DTS
                                DTSmodelXbrl = ModelXbrl.create(self.modelXbrl.modelManager, 
                                             newDocumentType=ModelDocument.Type.DTSENTRIES,
                                             url=self.uri[:-4] + "-" + ln + ".dts", isEntry=True)
                                DTSdoc = DTSmodelXbrl.modelDocument
                                DTSdoc.inDTS = True
                                for schemaRefElt in schemaRefElts:
                                    if schemaRefElt.hasAttributeNS(XbrlConst.xlink, "href"):
                                        doc = ModelDocument.load(DTSmodelXbrl,
                                                                 schemaRefElt.getAttributeNS(XbrlConst.xlink, "href"),
                                                                 base=self.baseForElement(schemaRefElt))
                                        DTSdoc.referencesDocument[doc] = "import"  #fake import
                                        doc.inDTS = True
                            if DTSmodelXbrl is not None:
                                setattr(self, ln, DTSmodelXbrl)
                    elif ln in ("namespaceRename", "roleChange"):   
                        modelObject = ModelVersObject.create(self, element)
                        if modelAction:
                            modelAction.events.append(modelObject)
                elif self.fromDTS is None or self.toDTS is None:
                    pass
                elif ns == XbrlConst.vercb:
                    if ln in ("conceptRename", "conceptAdd", "conceptDelete"):
                        modelObject = ModelVersObject.create(self, element)
                        if modelAction:
                            modelAction.events.append(modelObject)
                    if ln == "conceptRename":
                        modelObject.setConceptEquivalence()
                    elif ln == "conceptDelete":
                        actionRelatedFromMdlObjs.append(modelObject)
                    elif ln == "conceptAdd":
                        actionRelatedToMdlObjs.append(modelObject)
                elif ns == XbrlConst.verce:
                    if ln in ("conceptIDChange", "conceptTypeChange", "conceptSubstitutionGroupChange", 
                              "conceptDefaultChange", "conceptNillableChange",
                              "conceptAbstractChange", "conceptBlockChange", "conceptFixedChange",
                              "conceptFinalChange", "conceptPeriodTypeChange", "conceptBalanceChange",
                              "conceptAttributeAdd", "conceptAttributeDelete", "conceptAttributeChange", 
                              "tupleContentModelChange",
                              "conceptLabelAdd", "conceptLabelDelete", "conceptLabelChange",
                              "conceptReferenceAdd", "conceptReferenceDelete", "conceptReferenceChange"):
                        modelObject = ModelVersObject.create(self, element)
                        if modelAction:
                            modelAction.events.append(modelObject)
                elif ns == XbrlConst.verrels:
                    if ln in ("relationshipSetModelChange", "relationshipSetModelAdd", "relationshipSetModelDelete"):
                        modelObject = ModelVersObject.ModelRelationshipSetChange(self, element)
                        if modelAction:
                            modelAction.events.append(modelObject)
                        modelRelationshipSetEvent = modelObject
                    elif ln in ("fromRelationshipSet", "toRelationshipSet"):
                        modelObject = ModelVersObject.ModelRelationshipSet(self, element)
                        if modelRelationshipSetEvent:
                            modelRelationshipSet = modelObject
                            if ln == "fromRelationshipSet":
                                modelRelationshipSetEvent.fromRelationshipSet = modelObject
                            else:
                                modelRelationshipSetEvent.toRelationshipSet = modelObject
                            modelObject.modelRelationshipSetEvent = modelRelationshipSetEvent
                    elif ln == "relationships":
                        modelObject = ModelVersObject.ModelRelationships(self, element)
                        if modelRelationshipSet:
                            modelRelationshipSet.relationships.append(modelObject)
                            modelObject.modelRelationshipSet = modelRelationshipSet

                elif ns == XbrlConst.veria:
                    if ln in ("aspectModelChange", "aspectModelAdd", "aspectModelDelete"):
                        modelObject = ModelVersObject.ModelInstanceAspectsChange(self, element)
                        if modelAction:
                            modelAction.events.append(modelObject)
                        aspectModelEvent = modelObject
                    elif ln in ("fromAspects", "toAspects"):
                        modelObject = ModelVersObject.ModelInstanceAspects(self, element)
                        if aspectModelEvent:
                            modelAspects = modelObject
                            if ln == "fromAspects":
                                aspectModelEvent.fromAspects = modelObject
                            else:
                                aspectModelEvent.toAspects = modelObject
                            modelObject.aspectModelEvent = aspectModelEvent
                    elif ln in ("concept", "explicitDimension", "typedDimension", "segment", "scenario", 
                                "entityIdentifier", "period", "location", "unit"):
                        modelObject = ModelVersObject.ModelInstanceAspect(self, element)
                        modelAspect = modelObject
                        if modelAspects:
                            modelAspects.aspects.append(modelObject)
                        modelObject.modelAspects = modelAspects
                        modelMulDivBy = None
                    elif ln in ("member", "startDate", "endDate", "instant", "forever", "multiplyBy", "divideBy"):
                        modelObject = ModelVersObject.ModelInstanceMemberAspect(self, element)
                        if modelAspect:
                            modelAspect.members.append(modelObject)
                        modelObject.modelAspect = modelAspect
                        if ln.endswith("By"):
                            modelMulDivBy = modelObject
                    elif ln == "measure":
                        modelObject = ModelVersObject.ModelInstanceMemberAspect(self, element)
                        if modelMulDivBy:
                            modelMulDivBy.members.append(modelObject)
                            modelObject.modelAspect = modelMulDivBy
                        elif modelAspect:
                            modelAspect.members.append(modelObject)
                            modelObject.modelAspect = modelAspect
                    
                        
                # save document objects indexed by id
                if element.hasAttribute("id"):
                    if modelObject is None:
                        modelObject = ModelVersObject.create(self, element)
                    self.idObjects[element.getAttribute("id")] = modelObject
            ModelVersObject.relateConceptMdlObjs(self, actionRelatedFromMdlObjs, actionRelatedToMdlObjs)
            # do linkbaseRef's at end after idObjects all loaded
            for element in rootElement.getElementsByTagNameNS(XbrlConst.link,"linkbaseRef"):
                self.schemaLinkbaseRefDiscover(element)
        except (ValueError, LookupError) as err:
            self.modelXbrl.modelManager.addToLog("discovery: {0} error {1}".format(
                        os.path.basename(self.uri),
                        err))
            
    def entryURIs(self, DTS):
        if DTS.modelDocument:
            if DTS.modelDocument.type == ModelDocument.Type.DTSENTRIES:
                return sorted([mdlDoc.uri for mdlDoc in DTS.modelDocument.referencesDocument.keys()])
            else:
                return [DTS.uri]
        return []
    
    def diffDTSes(self, versReportFile, fromDTS, toDTS, reason="technical"):
        self.uri = os.path.normpath(versReportFile)
        self.fromDTS = fromDTS
        self.toDTS = toDTS
        reason = reason.lower()
        if ":" in reason: categoryType = reason
        elif reason.startswith("technical"): categoryType = "technicalCategory"
        elif reason.startswith("business"): categoryType = "businessCategory"
        else: categoryType = "errataCategory"
        self.xmlDocument = xml.dom.minidom.parseString(
            '<?xml version="1.0" encoding="UTF-8"?>' 
            '<report' 
            '  xmlns="http://xbrl.org/2010/versioning-base"' 
            '  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"' 
            '  xmlns:link="http://www.xbrl.org/2003/linkbase"' 
            '  xmlns:xlink="http://www.w3.org/1999/xlink"' 
            '  xsi:schemaLocation="' 
                'http://xbrl.org/2010/versioning-base http://xbrl.org/2010/versioning-base ' 
                'http://xbrl.org/2010/versioning-concept-basic http://xbrl.org/2010/versioning-concept-basic ' 
                'http://xbrl.org/2010/versioning-concept-extended http://xbrl.org/2010/versioning-concept-extended ' 
            '">' 
                '<!-- link:linkbaseRef xlink:type="simple"' 
                '  xlink:arcrole="http://www.w3.org/1999/xlink/properties/linkbase"' 
                '  xlink:title="documentation"' 
                '  xlink:href="sample.xml"/ -->' 
                '<fromDTS>{0}</fromDTS>' 
                '<toDTS>{1}</toDTS>' 
                '<assignment id="versioningTask"><{2}/></assignment>' 
            '</report>'.format(
                ''.join(['<link:schemaRef xlink:type="simple" xlink:href="{0}"/>'.format(self.relativeUri(uri))
                           for uri in self.entryURIs(fromDTS)]),
                ''.join(['<link:schemaRef xlink:type="simple" xlink:href="{0}"/>'.format(self.relativeUri(uri))
                           for uri in self.entryURIs(toDTS)]),
                categoryType)
             )
        self.xmlDocument.modelDocument = self
        self.reportElement = XmlUtil.child(self.xmlDocument, XbrlConst.ver, "report")
        self.actionNum = 1
        
        self.modelXbrl.modelManager.showStatus(_("Comparing namespaces"))
        self.diffNamespaces()
        self.modelXbrl.modelManager.showStatus(_("Comparing roles"))
        self.diffRoles()
        self.modelXbrl.modelManager.showStatus(_("Comparing concepts"))
        self.diffConcepts()
        for arcroleUri in (XbrlConst.parentChild, XbrlConst.summationItem, XbrlConst.essenceAlias, XbrlConst.requiresElement, XbrlConst.generalSpecial):
            self.modelXbrl.modelManager.showStatus(_("Comparing {0} relationships").format(os.path.basename(arcroleUri)))
            self.diffRelationshipSet(arcroleUri)
            
        self.modelXbrl.modelManager.showStatus(_("Comparing dimension defaults"))
        self.diffDimensionDefaults()
        
        self.modelXbrl.modelManager.showStatus(_("Comparing explicit dimensions"))
        self.diffDimensions()
        
        self.modelXbrl.modelManager.showStatus(_("Checking report file"))
        self.modelXbrl.modelDocument = self # model document is now established
        self.versioningReportDiscover(self.reportElement)
        self.modelXbrl.modelManager.showStatus(_("Writing report file"))
        with open(versReportFile, "w", encoding="utf-8") as fh:
            XmlUtil.writexml(fh, self.xmlDocument, encoding="utf-8")
        self.filepath = versReportFile
        self.modelXbrl.modelManager.showStatus(_("C report file"))
        self.modelXbrl.modelManager.showStatus(_("ready"), 2000)
        
    def diffNamespaces(self):
        # build fomr and to lists based on namespaces
        fromNSes = set()
        toNSes = set()
        for fromModelDoc in self.fromDTS.urlDocs.values():
            if fromModelDoc.type == ModelDocument.Type.SCHEMA:
                fromNSes.add(fromModelDoc.targetNamespace)
        for toModelDoc in self.toDTS.urlDocs.values():
            if toModelDoc.type == ModelDocument.Type.SCHEMA:
                toNSes.add(toModelDoc.targetNamespace)
        self.diffURIs( fromNSes, toNSes, 
                       "namespaceRename",
                       (self.roleNumlessMatchPattern, self.rolePathlessMatchPattern, self.roleNoFromToMatchPattern),
                        self.namespaceRenameFrom, self.namespaceRenameTo)
    
    def diffRoles(self):
        self.diffURIs( set( self.fromDTS.roleTypes.keys() ),
                       set( self.toDTS.roleTypes.keys() ),
                       "roleChange", 
                       (self.roleNumlessMatchPattern, self.rolePathlessMatchPattern, self.roleNoFromToMatchPattern),
                       self.roleChangeFrom, self.roleChangeTo )
                    
    def diffURIs(self, fromURIs, toURIs, eventName, matchers, changeFrom, changeTo):
        # remove common roles from each
        commonRoles = fromURIs & toURIs
        fromURIs -= commonRoles
        toURIs -= commonRoles
        for matcher in matchers:
            # look for roles matching on matcher subpattern
            fromMatchURIs = defaultdict(list)
            toMatchURIs = defaultdict(list)
            # try to URIs based on numbers in uri path removed (e.g., ignoring dates)
            for matchURIs, origURIs in ((fromMatchURIs,fromURIs),(toMatchURIs,toURIs)):
                for uri in origURIs:
                    matchURIs[matcher(uri)].append(uri)
            for fromMatchURI, fromMatchedURIs in fromMatchURIs.items():
                for toURI in toMatchURIs.get(fromMatchURI,[]):
                    for fromURI in fromMatchedURIs:
                        self.createBaseEvent(eventName, fromURI, toURI)
                        changeFrom[fromURI] = toURI
                        changeTo[toURI] = fromURI
                        # removed from consideration by next pass on final path segment
                        fromURIs.discard(fromURI)
                        toURIs.discard(toURI)
                
    def uriNumlessMatchPattern(self, uri):
        # remove date and numbers from uri (for now, more sophisticated later)
        return ''.join((c if str.isalpha(c) or c == '/' else '') for c in uri)

    def roleNumlessMatchPattern(self, role):
        # remove date and numbers from role except last path segment
        basepart, sep, lastpart = role.rpartition("/")
        return ''.join((c if str.isalpha(c) or c == '/' else '') for c in basepart) + \
                ((sep + lastpart) if lastpart else "")

    def rolePathlessMatchPattern(self, role):
        # remove intermediate role path elements between authority and end path segment
        basepart, sep, lastpart = role.rpartition("/")
        return UrlUtil.authority(role) + ((sep + lastpart) if lastpart else "")

    def roleNoFromToMatchPattern(self, role):
        # remove intermediate role path elements between authority and end path segment
        # for roland test case generation
        basepart, sep, lastpart = role.rpartition("/")
        if lastpart.endswith("_to"):
            lastpart = lastpart[:-3]
        elif lastpart.endswith("_from"):
            lastpart = lastpart[:-5]
        return UrlUtil.authority(role) + ((sep + lastpart) if lastpart else "")

    def diffConcepts(self):
        toConceptsMatched = set()
        vercb = XbrlConst.vercb
        verce = XbrlConst.verce
        for fromConceptQname, fromConcept in self.fromDTS.qnameConcepts.items():
            if not fromConcept.isItem and not fromConcept.isTuple: 
                continue
            toConceptQname = self.toDTSqname(fromConceptQname)
            if toConceptQname in self.toDTS.qnameConcepts:
                toConcept = self.toDTS.qnameConcepts[toConceptQname]
                toConceptsMatched.add(toConceptQname)
                # compare concepts
                action = None # keep same action for all of same concept's changes
                if fromConcept.id != toConcept.id:
                    action = self.createConceptEvent(verce, "verce:conceptIDChange", fromConcept, toConcept, action, fromValue=fromConcept.id, toValue=toConcept.id)
                if fromConcept.substitutionGroupQname != self.fromDTSqname(toConcept.substitutionGroupQname):
                    action = self.createConceptEvent(verce, "verce:conceptSubstitutionGroupChange", fromConcept, toConcept, action, fromValue=fromConcept.substitutionGroupQname, toValue=self.toDTSqname(toConcept.substitutionGroupQname))
                if fromConcept.isItem and toConcept.isItem:
                    if fromConcept.typeQname != self.fromDTSqname(toConcept.typeQname):
                        action = self.createConceptEvent(verce, "verce:conceptTypeChange", fromConcept, toConcept, action, fromValue=fromConcept.typeQname, toValue=toConcept.typeQname)
                    if fromConcept.nillable != toConcept.nillable:
                        action = self.createConceptEvent(verce, "verce:conceptNillableChange", fromConcept, toConcept, action, fromValue=fromConcept.nillable, toValue=toConcept.nillable)
                    if fromConcept.abstract != toConcept.abstract:
                        action = self.createConceptEvent(verce, "verce:conceptAbstractChange", fromConcept, toConcept, action, fromValue=fromConcept.abstract, toValue=toConcept.abstract)
                    if fromConcept.block != toConcept.block:
                        action = self.createConceptEvent(verce, "verce:conceptBlockChange", fromConcept, toConcept, action, fromValue=fromConcept.block, toValue=toConcept.block)
                    if fromConcept.default != toConcept.default:
                        action = self.createConceptEvent(verce, "verce:conceptDefaultChange", fromConcept, toConcept, action, fromValue=fromConcept.default, toValue=toConcept.default)
                    if fromConcept.fixed != toConcept.fixed:
                        action = self.createConceptEvent(verce, "verce:conceptFixedChange", fromConcept, toConcept, action, fromValue=fromConcept.fixed, toValue=toConcept.fixed)
                    if fromConcept.final != toConcept.final:
                        action = self.createConceptEvent(verce, "verce:conceptFinalChange", fromConcept, toConcept, action, fromValue=fromConcept.final, toValue=toConcept.final)
                    if fromConcept.periodType != toConcept.periodType:
                        action = self.createConceptEvent(verce, "verce:conceptPeriodTypeChange", fromConcept, toConcept, action, fromValue=fromConcept.periodType, toValue=toConcept.periodType)
                    if fromConcept.balance != toConcept.balance:
                        action = self.createConceptEvent(verce, "verce:conceptBalanceChange", fromConcept, toConcept, action, fromValue=fromConcept.balance, toValue=toConcept.balance)
                if fromConcept.isTuple and toConcept.isTuple:
                    fromType = fromConcept.type # it is null for xsd:anyType
                    toType = toConcept.type
                    # TBD change to xml comparison with namespaceURI mappings, prefixes ignored
                    if fromType and toType and fromType.element.toxml() != toType.element.toxml():
                        action = self.createConceptEvent(verce, "verce:tupleContentModelChange", fromConcept, toConcept, action)
                # custom attributes in from Concept
                fromCustAttrs = {}
                toCustAttrs = {}
                for concept, attrs in ((fromConcept,fromCustAttrs),(toConcept,toCustAttrs)):
                    for i in range(len(concept.element.attributes)):
                        attr = concept.element.attributes.item(i)
                        if (attr.name not in ("abstract","block","default","final","fixed","form","id","maxOccurs",
                                             "minOccurs","name","nillable","ref","substitutionGroup","type") and 
                            attr.prefix != "xmlns" and 
                            attr.namespaceURI != XbrlConst.xbrli and 
                            attr.namespaceURI != XbrlConst.xbrldt):
                            attrs[concept.prefixedNameQname(attr.name)] = attr.value
                for attr in fromCustAttrs.keys():
                    if attr not in toCustAttrs:
                        action = self.createConceptEvent(verce, "verce:conceptAttributeDelete", fromConcept, None, action, fromCustomAttribute=attr, fromValue=fromCustAttrs[attr])
                    elif fromCustAttrs[attr] != toCustAttrs[attr]:
                        action = self.createConceptEvent(verce, "verce:conceptAttributeChange", fromConcept, toConcept, action, fromCustomAttribute=attr, toCustomAttribute=attr, fromValue=fromCustAttrs[attr], toValue=toCustAttrs[attr])
                for attr in toCustAttrs.keys():
                    if attr not in fromCustAttrs:
                        action = self.createConceptEvent(verce, "verce:conceptAttributeAdd", None, toConcept, action, toCustomAttribute=attr, toValue=toCustAttrs[attr])
                        
                # labels, references from each concept
                for event, arcroles in (("verce:conceptLabel", (XbrlConst.conceptLabel, XbrlConst.elementLabel)),
                                        ("verce:conceptReference", (XbrlConst.conceptReference, XbrlConst.elementReference))):
                    fromResources = {}
                    toResources = {}
                    for dts, concept, resources in ((self.fromDTS, fromConcept, fromResources),
                                                    (self.toDTS, toConcept, toResources)):
                        for arcrole in arcroles:
                            resourcesRelationshipSet = dts.relationshipSet(arcrole)
                            if resourcesRelationshipSet:
                                for rel in resourcesRelationshipSet.fromModelObject(concept):
                                    resource = rel.toModelObject
                                    key = (rel.linkrole, arcrole, resource.role, resource.xmlLang,
                                           rel.linkQname, rel.qname, resource.qname) + \
                                           XbrlUtil.attributes(dts, None, rel.element,
                                                exclusions=(XbrlConst.xlink, "use","priority","order","id")) + \
                                           XbrlUtil.attributes(dts, None, resource.element,
                                                exclusions=(XbrlConst.xlink))
                                    resources[key] = resource
                    for key,label in fromResources.items():
                        fromText = label.innerText
                        if key not in toResources:
                            action = self.createConceptEvent(verce, event + "Delete", fromConcept, None, action, fromResource=label, fromResourceText=fromText)
                        else:
                            toLabel = toResources[key]
                            toText = toLabel.innerText
                            if not XbrlUtil.sEqual(self.fromDTS, label.element, toLabel.element, excludeIDs=True, dts2=self.toDTS, ns2ns1Tbl=self.namespaceRenameTo):
                                action = self.createConceptEvent(verce, event + "Change", fromConcept, toConcept, action, fromResource=label, toResource=toResources[key], fromResourceText=fromText, toResourceText=toText)
                    for key,label in toResources.items():
                        toText = label.innerText
                        if key not in fromResources:
                            action = self.createConceptEvent(verce, event + "Add", None, toConcept, action, toResource=label, toResourceText=toText)

                        

                # 
            else:
                self.createConceptEvent(vercb, "vercb:conceptDelete", fromConcept=fromConcept)
        for toConceptQname, toConcept in self.toDTS.qnameConcepts.items():
            if ((toConcept.isItem or toConcept.isTuple) and
                 toConceptQname not in toConceptsMatched):
                self.createConceptEvent(vercb, "vercb:conceptAdd", toConcept=toConcept)
            
    def diffRelationshipSet(self, arcrole):
        # compare ELRs for new/removed
        fromLinkRoleUris = set()
        toLinkRoleUris = set()
        for dts, linkRoleUris in ((self.fromDTS, fromLinkRoleUris), 
                                  (self.toDTS, toLinkRoleUris) ):
            for linkroleUri in dts.relationshipSet(arcrole).linkRoleUris:
                linkRoleUris.add(linkroleUri)
        # removed, added ELRs
        for dts, linkRoleUris, otherRoleUris, roleChanges, e1, e2, isFrom in (
                        (self.fromDTS, fromLinkRoleUris, toLinkRoleUris, self.roleChangeFrom, "relationshipSetModelDelete", "fromRelationshipSet", True),
                        (self.toDTS, toLinkRoleUris, fromLinkRoleUris, self.roleChangeTo, "relationshipSetModelAdd", "toRelationshipSet", False)):
            for linkRoleUri in linkRoleUris:
                if not (linkRoleUri in otherRoleUris or linkRoleUri in roleChanges):
                    # fromUri tree is removed
                    relSetEvent = None
                    relationshipSet = dts.relationshipSet(arcrole, linkRoleUri)
                    for rootConcept in relationshipSet.rootConcepts:
                        if relSetEvent is None:
                            relSetMdlEvent = self.createRelationshipSetEvent(e1)
                            relSetEvent = self.createRelationshipSetEvent(e2, eventParent=relSetMdlEvent)
                        rs = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=linkRoleUri, arcrole=arcrole)
                        self.createRelationshipSetEvent("relationships", eventParent=rs, fromConcept=rootConcept, axis="descendant-or-self", comment="root relationship")
                elif isFrom:  # role in both, compare hierarchies
                    self.relSetAddedEvent = None
                    self.relSetDeletedEvent = None
                    otherLinkRoleUri = roleChanges[linkRoleUri] if linkRoleUri in roleChanges else linkRoleUri
                    fromRelationshipSet = dts.relationshipSet(arcrole, linkRoleUri)
                    toRelationshipSet = self.toDTS.relationshipSet(arcrole, otherLinkRoleUri)
                    fromRoots = fromRelationshipSet.rootConcepts
                    toRoots = toRelationshipSet.rootConcepts
                    for fromRoot in fromRoots:
                        toRootConcept = self.toDTS.qnameConcepts.get(self.toDTSqname(fromRoot.qname))
                        if toRootConcept and toRootConcept not in toRoots: # added qname
                            if self.relSetDeletedEvent is None:
                                relSetMdlEvent = self.createRelationshipSetEvent("relationshipSetModelDelete")
                                relSetEvent = self.createRelationshipSetEvent("fromRelationshipSet", eventParent=relSetMdlEvent)
                                self.relSetDeletedEvent = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=linkRoleUri, arcrole=arcrole)
                            self.createRelationshipSetEvent("relationships", eventParent=self.relSetDeletedEvent, fromConcept=fromRoot, axis="descendant-or-self")
                        else:
                            # check hierarchies
                            self.diffRelationships(fromRoot, toRootConcept, fromRelationshipSet, toRelationshipSet)
                    for toRoot in toRoots:
                        fromRootConcept = self.toDTS.qnameConcepts.get(self.fromDTSqname(toRoot.qname))
                        if fromRootConcept and fromRootConcept not in fromRoots: # added qname
                            if self.relSetAddedEvent is None:
                                relSetMdlEvent = self.createRelationshipSetEvent("relationshipSetModelAdd")
                                relSetEvent = self.createRelationshipSetEvent("toRelationshipSet", eventParent=relSetMdlEvent)
                                self.relSetAddedEvent = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=toRelationshipSet.linkrole, arcrole=toRelationshipSet.arcrole)
                            self.createRelationshipSetEvent("relationships", eventParent=self.relSetAddedEvent, fromConcept=toRoot, axis="descendant-or-self", comment="root relationship")

    def diffRelationships(self, fromConcept, toConcept, fromRelationshipSet, toRelationshipSet):
        fromRels = fromRelationshipSet.fromModelObject(fromConcept)
        toRels = toRelationshipSet.fromModelObject(toConcept)
        for i, fromRel in enumerate(fromRels):
            fromTgtConcept = fromRel.toModelObject
            toTgtQname = self.toDTSqname(fromTgtConcept.qname) if fromTgtConcept else None
            toRel = toRels[i] if i < len(toRels) else None
            if toRel and toRel.toModelObject and toRel.toModelObject.qname == toTgtQname:
                fromRelAttrs = XbrlUtil.attributes(self.modelXbrl, None, fromRel.element,
                     exclusions=relationshipSetArcAttributesExclusion)
                toRelAttrs = XbrlUtil.attributes(self.modelXbrl, None, toRel.element,
                     exclusions=relationshipSetArcAttributesExclusion,
                     ns2ns1Tbl=self.namespaceRenameTo)
                if fromRelAttrs != toRelAttrs:
                    fromAttrsSet = set(fromRelAttrs)
                    toAttrsSet = set(toRelAttrs)
                    relSetMdlEvent = self.createRelationshipSetEvent("relationshipSetModelChange")
                    relSetEvent = self.createRelationshipSetEvent("fromRelationshipSet", eventParent=relSetMdlEvent)
                    relSetChangedEvent = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=fromRelationshipSet.linkrole, arcrole=fromRelationshipSet.arcrole)
                    self.createRelationshipSetEvent("relationships", eventParent=relSetChangedEvent, fromConcept=fromConcept, toConcept=fromTgtConcept, attrValues=fromAttrsSet-toAttrsSet)
                    relSetEvent = self.createRelationshipSetEvent("toRelationshipSet", eventParent=relSetMdlEvent)
                    relSetChangedEvent = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=toRelationshipSet.linkrole, arcrole=toRelationshipSet.arcrole)
                    self.createRelationshipSetEvent("relationships", eventParent=relSetChangedEvent, fromConcept=toConcept, toConcept=toRel.toModelObject, attrValues=toAttrsSet-fromAttrsSet)
                else:
                    self.diffRelationships(fromTgtConcept, toRel.toModelObject, fromRelationshipSet, toRelationshipSet)
            else:
                if self.relSetDeletedEvent is None:
                    relSetMdlEvent = self.createRelationshipSetEvent("relationshipSetModelDelete")
                    relSetEvent = self.createRelationshipSetEvent("fromRelationshipSet", eventParent=relSetMdlEvent)
                    self.relSetDeletedEvent = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=fromRelationshipSet.linkrole, arcrole=fromRelationshipSet.arcrole)
                if toRel:
                    comment = _('corresponding relationship {0} toDTS toName="{1}"').format(i+1, XmlUtil.addQnameValue(self.reportElement, toRel.toModelObject.qname))
                else:
                    comment = _('toDTS does not have a corresponding relationship at position {0}'.format(i+1))
                self.createRelationshipSetEvent("relationships", eventParent=self.relSetDeletedEvent, fromConcept=fromConcept, toConcept=fromTgtConcept, comment=comment)
        for i, toRel in enumerate(toRels):
            toTgtConcept = toRel.toModelObject
            fromTgtQname = self.fromDTSqname(toTgtConcept.qname) if toRel.toModelObject else None
            fromRel = fromRels[i] if i < len(fromRels) else None
            if not fromRel or not fromRel.toModelObject or fromRel.toModelObject.qname != fromTgtQname:
                if self.relSetAddedEvent is None:
                    relSetMdlEvent = self.createRelationshipSetEvent("relationshipSetModelAdd")
                    relSetEvent = self.createRelationshipSetEvent("toRelationshipSet", eventParent=relSetMdlEvent)
                    self.relSetAddedEvent = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=toRelationshipSet.linkrole, arcrole=toRelationshipSet.arcrole)
                if fromRel:
                    comment = _('corresponding relationship {0} toDTS toName="{1}"').format(i+1, XmlUtil.addQnameValue(self.reportElement, fromRel.toModelObject.qname))
                else:
                    comment = _('fromDTS does not have a corresponding relationship at position {0}'.format(i+1))
                self.createRelationshipSetEvent("relationships", eventParent=self.relSetAddedEvent, fromConcept=toConcept, toConcept=toTgtConcept, comment=comment)
    
    def diffDimensionDefaults(self):
        # dimension-defaults are global
        fromDimDefaults = {}
        toDimDefaults = {}
        for dts, dimDefaults in ((self.fromDTS, fromDimDefaults), 
                                  (self.toDTS, toDimDefaults) ):
            for rel in dts.relationshipSet(XbrlConst.dimensionDefault).modelRelationships:
                dimDefaults[rel.fromModelObject.qname] = rel.toModelObject.qname
        # removed, added defaults
        for dts, dimDefaults, otherDimDefaults, otherDTSqname, e1, e2 in (
                        (self.fromDTS, fromDimDefaults, toDimDefaults, self.toDTSqname, "aspectModelDelete", "fromAspects"),
                        (self.toDTS, toDimDefaults, fromDimDefaults, self.fromDTSqname, "aspectModelAdd", "toAspects")):
            aspectEvent = None
            for fromDimQname, fromDefaultQname in dimDefaults.items():
                otherDTSDimQname = otherDTSqname(fromDimQname)
                otherDTSDefaultQname = otherDTSqname(fromDefaultQname)
                if otherDTSDimQname not in otherDimDefaults or otherDimDefaults[otherDTSDimQname] != otherDTSDefaultQname:
                    # dim default is removed
                    if aspectEvent is None:
                        aspectMdlEvent = self.createInstanceAspectsEvent(e1)
                        aspectEvent = self.createInstanceAspectsEvent(e2, eventParent=aspectMdlEvent)
                    explDim = self.createInstanceAspectsEvent("explicitDimension", (('name',fromDimQname),), eventParent=aspectEvent)
                    self.createInstanceAspectsEvent("member", (('name',fromDefaultQname),('isDefaultMember','true')), eventParent=explDim, comment="dimension default")
    
    def diffDimensions(self):
        # DRS rels by (primary item,linkrole) of the has-hypercube relationship
        fromDRSrels = defaultdict(list)
        toDRSrels = defaultdict(list)
        for dts, DRSrels in ((self.fromDTS, fromDRSrels), (self.toDTS, toDRSrels)):
            for hasHcArcrole in (XbrlConst.all, XbrlConst.notAll):
                for DRSrel in dts.relationshipSet(hasHcArcrole).modelRelationships:
                    DRSrels[DRSrel.fromModelObject.qname,DRSrel.linkrole].append( DRSrel )
        # removed, added pri item dimensions
        for dts, DRSrels, otherDTS, otherDRSrels, otherDTSqname, roleChanges, e1, e2, isFrom in (
                        (self.fromDTS, fromDRSrels, self.toDTS, toDRSrels, self.toDTSqname, self.roleChangeFrom, "aspectModelDelete", "fromAspects", True),
                        (self.toDTS, toDRSrels, self.fromDTS, fromDRSrels, self.fromDTSqname, self.roleChangeTo, "aspectModelAdd", "toAspects", False)):
            aspectEvent = None
            for DRSkey, priItemDRSrels in DRSrels.items():
                priItemQname, linkrole = DRSkey
                priItemConcept = dts.qnameConcepts.get(priItemQname)
                otherDTSpriItemQname = otherDTSqname(priItemQname)
                otherDTSpriItemConcept = otherDTS.qnameConcepts.get(otherDTSpriItemQname)
                otherLinkrole = roleChanges[linkrole] if linkrole in roleChanges else linkrole
                otherDTSpriItemDRSrels = otherDRSrels.get((otherDTSpriItemQname, otherLinkrole))
                # all dimensions in these DRSes are anded together
                addDelEvent = changeEvent = False
                if not otherDTSpriItemDRSrels: #every dim for this pri item is added/removed
                    aspectMdlEvent = self.createInstanceAspectsEvent(e1)
                    aspectEvent = self.createInstanceAspectsEvent(e2, eventParent=aspectMdlEvent)
                    priItemInheritRels = dts.relationshipSet(XbrlConst.domainMember, linkrole).fromModelObject(priItemConcept)
                    priItem = self.createInstanceAspectsEvent("concept", 
                                                              (('name',priItemQname),) + \
                                                              ((('linkrole',linkrole),
                                                                ('arcrole',XbrlConst.domainMember),
                                                               ('axis', 'DRS-descendant-or-self')) if priItemInheritRels else ()),
                                                               eventParent=aspectEvent)
                    for dimRel, isNotAll, isClosed in self.DRSdimRels(dts, priItemDRSrels):
                        dimConcept = dimRel.toModelObject
                        explDim = self.createInstanceAspectsEvent("typedDimension" if dimConcept.isTypedDimension else "explicitDimension", 
                                                                  (('name',dimConcept.qname),) + \
                                                                  ((('excluded','true'),) if isNotAll else ()),
                                                                  eventParent=aspectEvent)
                        for domRel in self.DRSdomRels(dts, dimRel):
                            domHasMemRels = dts.relationshipSet(XbrlConst.domainMember, linkrole).fromModelObject(priItemConcept)
                            self.createInstanceAspectsEvent("member", (('name',domRel.toModelObject.qname),) + \
                                                                      ((('linkrole',domRel.linkrole),
                                                                        ('arcrole',XbrlConst.domainMember),
                                                                        ('axis', 'DRS-descendant-or-self')) if domHasMemRels else ()),
                                                                      eventParent=explDim)
                elif isFrom: # pri item in both, differences are found
                    # hypercube differences
                    hcDifferences = self.DRShcDiff(dts, priItemDRSrels, otherDTS, otherDTSpriItemDRSrels)
                    if hcDifferences:
                        relSetMdlEvent = self.createRelationshipSetEvent("relationshipSetModelChange")
                        for fromHcRel, toHcRel, fromAttrsSet, toAttrsSet in hcDifferences:
                            relSetEvent = self.createRelationshipSetEvent("fromRelationshipSet", eventParent=relSetMdlEvent)
                            relSetChangedEvent = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=fromHcRel.linkrole, arcrole=fromHcRel.arcrole)
                            self.createRelationshipSetEvent("relationships", eventParent=relSetChangedEvent, fromConcept=fromHcRel.fromModelObject, toConcept=fromHcRel.toModelObject, attrValues=fromAttrsSet-toAttrsSet)
                            relSetEvent = self.createRelationshipSetEvent("toRelationshipSet", eventParent=relSetMdlEvent)
                            relSetChangedEvent = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=toHcRel.linkrole, arcrole=toHcRel.arcrole)
                            self.createRelationshipSetEvent("relationships", eventParent=relSetChangedEvent, fromConcept=toHcRel.toModelObject, toConcept=toHcRel.toModelObject, attrValues=toAttrsSet-fromAttrsSet)
                    priItemDifferences = self.DRSdiff(priItemConcept, linkrole, otherDTSpriItemConcept, otherLinkrole, XbrlConst.domainMember)
                    if priItemDifferences:
                        for fromRel, toRel, fromAttrSet, toAttrSet in priItemDifferences:
                            if fromRel:
                                if toRel: e = "aspectModelChange"
                                else:     e = "aspectModelAdd"
                            else:         e = "aspectModelDelete"
                            aspectMdlEvent = self.createInstanceAspectsEvent(e)
                            for rel, attrSet, e in ((fromRel, fromAttrSet-toAttrSet, "fromAspects"),
                                                    (toRel, toAttrSet-fromAttrSet, "toAspects")):
                                if rel:
                                    aspectEvent = self.createInstanceAspectsEvent(e, eventParent=aspectMdlEvent)
                                    priItemInheritRels = dts.relationshipSet(XbrlConst.domainMember, linkrole).fromModelObject(priItemConcept)
                                    priItem = self.createInstanceAspectsEvent("concept", 
                                                                              (('name',priItemQname),) + \
                                                                              ((('linkrole',rel.linkrole),
                                                                                ('arcrole',XbrlConst.domainMember),
                                                                               ('axis', 'DRS-descendant-or-self')) if priItemInheritRels else ()),
                                                                               eventParent=aspectEvent)
                                    for dimRel, isNotAll, isClosed in self.DRSdimRels(dts, priItemDRSrels):
                                        dimConcept = dimRel.toModelObject
                                        explDim = self.createInstanceAspectsEvent("typedDimension" if dimConcept.isTypedDimension else "explicitDimension",
                                                                                  (('name',dimConcept.qname),) + \
                                                                                  ((('excluded','true'),) if isNotAll else ()),
                                                                                  eventParent=aspectEvent)
                                        for domRel in self.DRSdomRels(dts, dimRel):
                                            domHasMemRels = dts.relationshipSet(XbrlConst.domainMember, linkrole).fromModelObject(priItemConcept)
                                            self.createInstanceAspectsEvent("member", (('name',domRel.toModelObject.qname),) + \
                                                                                      ((('linkrole',rel.linkrole),
                                                                                        ('arcrole',XbrlConst.domainMember),
                                                                                        ('axis', 'DRS-descendant-or-self')) if domHasMemRels else ()),
                                                                                      eventParent=explDim)
                    dimsDifferences = self.DRSdimsDiff(dts, priItemDRSrels, otherDTS, otherDTSpriItemDRSrels)
                    if dimsDifferences:
                        for fromDimRel, toDimRel, isNotAll, mbrDiffs in dimsDifferences:
                            if fromDimRel:
                                if toDimRel: e = "aspectModelChange"
                                else:            e = "aspectModelAdd"
                            else:                e = "aspectModelDelete"
                            aspectMdlEvent = self.createInstanceAspectsEvent(e)
                            for dimRel, e, isFrom in ((fromDimRel, "fromAspects", True),
                                                      (toDimRel, "toAspects", False)):
                                if dimRel:
                                    aspectEvent = self.createInstanceAspectsEvent(e, eventParent=aspectMdlEvent)
                                    priItemInheritRels = dts.relationshipSet(XbrlConst.domainMember, linkrole).fromModelObject(priItemConcept)
                                    priItem = self.createInstanceAspectsEvent("concept", 
                                                                              (('name',priItemQname),) + \
                                                                              ((('linkrole',linkrole),
                                                                                ('arcrole',XbrlConst.domainMember),
                                                                               ('axis', 'DRS-descendant-or-self')) if priItemInheritRels else ()),
                                                                               eventParent=aspectEvent)
                                    dimConcept = dimRel.toModelObject
                                    explDim = self.createInstanceAspectsEvent("typedDimension" if dimConcept.isTypedDimension else "explicitDimension", 
                                                                              (('name',dimConcept.qname),) + \
                                                                              ((('excluded','true'),) if isNotAll else ()),
                                                                              eventParent=aspectEvent)
                                    if mbrDiffs:
                                        for fromRel, toRel, fromAttrSet, toAttrSet in mbrDiffs:
                                            if isFrom: rel = fromRel
                                            else:      rel = toRel
                                            if rel:
                                                domHasMemRels = dts.relationshipSet(XbrlConst.domainMember, rel.linkrole).fromModelObject(rel.toModelObject)
                                                self.createInstanceAspectsEvent("member", (('name',rel.toModelObject.qname),) + \
                                                                                          ((('linkrole',rel.linkrole),
                                                                                            ('arcrole',XbrlConst.domainMember),
                                                                                            ('axis', 'DRS-descendant-or-self')) if domHasMemRels else ()),
                                                                                          eventParent=explDim)
                                    else:
                                        for domRel in self.DRSdomRels(dts, dimRel):
                                            domHasMemRels = dts.relationshipSet(XbrlConst.domainMember, linkrole).fromModelObject(priItemConcept)
                                            self.createInstanceAspectsEvent("member", (('name',domRel.toModelObject.qname),) + \
                                                                                      ((('linkrole',rel.linkrole),
                                                                                        ('arcrole',XbrlConst.domainMember),
                                                                                        ('axis', 'DRS-descendant-or-self')) if domHasMemRels else ()),
                                                                                      eventParent=explDim)
                    
    
    def DRSdimRels(self, dts, priItemDRSrels):
        return [(dimRel, hcRel.arcrole == XbrlConst.notAll, hcRel.isClosed)
                for hcRel in priItemDRSrels
                for dimRel in dts.relationshipSet(XbrlConst.hypercubeDimension, hcRel.consecutiveLinkrole).fromModelObject(hcRel.toModelObject)]
                        
    def DRSdomRels(self, dts, dimRel):
        return dts.relationshipSet(XbrlConst.dimensionDomain, dimRel.consecutiveLinkrole).fromModelObject(dimRel.toModelObject)
    
    def DRSdiff(self, fromConcept, fromLinkrole, toConcept, toLinkrole, arcrole, diffs=None):
        if diffs is None: diffs = []
        fromRels = self.fromDTS.relationshipSet(arcrole, fromLinkrole).fromModelObject(fromConcept)
        toRels = self.toDTS.relationshipSet(arcrole, toLinkrole).fromModelObject(toConcept)
        if arcrole == XbrlConst.dimensionDomain: arcrole = XbrlConst.domainMember #consec rel set
        for i, fromRel in enumerate(fromRels):
            fromTgtConcept = fromRel.toModelObject
            toTgtQname = self.toDTSqname(fromTgtConcept.qname) if fromTgtConcept else None
            toRel = toRels[i] if i < len(toRels) else None
            if toRel and toRel.toModelObject and toRel.toModelObject.qname == toTgtQname:
                toTgtConcept = toRel.toModelObject
                fromRelAttrs = XbrlUtil.attributes(self.modelXbrl, None, fromRel.element,
                     exclusions=relationshipSetArcAttributesExclusion)
                toRelAttrs = XbrlUtil.attributes(self.modelXbrl, None, toRel.element,
                     exclusions=relationshipSetArcAttributesExclusion,
                     ns2ns1Tbl=self.namespaceRenameTo)
                if fromRelAttrs != toRelAttrs:
                    diffs.append((fromRel, toRel, set(fromRelAttrs), set(toRelAttrs)))
                else:
                    self.DRSdiff(fromTgtConcept, fromRel.consecutiveLinkrole,
                                 toTgtConcept, toRel.consecutiveLinkrole,
                                 arcrole, diffs)
            else:
                diffs.append((fromRel, None, None, None))
        for i, toRel in enumerate(toRels):
            toTgtConcept = toRel.toModelObject
            fromTgtQname = self.fromDTSqname(toTgtConcept.qname) if toRel.toModelObject else None
            fromRel = fromRels[i] if i < len(fromRels) else None
            if not fromRel or not fromRel.toModelObject or fromRel.toModelObject.qname != fromTgtQname:
                diffs.append((None, toRel, None, None))
        return diffs
    
    def DRShcDiff(self, fromDTS, fromPriItemDRSrels, toDTS, toPriItemDRSrels):
        fromHcRels = {}
        toHcRels = {}
        for dts, priItemDRSrels, hcRels in ((fromDTS, fromPriItemDRSrels, fromHcRels), (toDTS, toPriItemDRSrels, toHcRels)):
            for hcRel in priItemDRSrels:
                hcRels[hcRel.fromModelObject, hcRel.toModelObject, hcRel.arcrole == XbrlConst.notAll] = hcRel
        diffs = []
        for i, fromHcRelKey in enumerate(fromHcRels.keys()):
            fromPriItemQname, fromHcQname, isNotAll = fromHcRelKey
            toPriItemQname = self.toDTSqname(fromPriItemQname)
            toHcQname = self.toDTSqname(fromHcQname)
            try:
                toHcRel = fromHcRels[toPriItemQname, toHcQname, isNotAll]
                fromHcRel = fromHcRels[fromHcRelKey]
                fromRelAttrs = XbrlUtil.attributes(self.modelXbrl, None, fromHcRel.element,
                     exclusions=relationshipSetArcAttributesExclusion)
                toRelAttrs = XbrlUtil.attributes(self.modelXbrl, None, toHcRel.element,
                     exclusions=relationshipSetArcAttributesExclusion,
                     ns2ns1Tbl=self.namespaceRenameTo)
                if fromRelAttrs != toRelAttrs:
                    diffs.append( (fromHcRel, toHcRel, set(fromRelAttrs), set(toRelAttrs)) )
            except KeyError:
                pass # not tracking addition or removal of hypercubes
        return diffs
    
    def typedDomainIsDifferent(self, fromDimConcept, toDimConcept):
        try:
            return self.typedDomainsCorrespond[fromDimConcept, toDimConcept]
        except KeyError:
            fromTypedDomain = fromDimConcept.typedDomainElement
            toTypedDomain = toDimConcept.typedDomainElement
            isCorresponding = (fromTypedDomain and toTypedDomain and
                               XbrlUtil.sEqual(self.fromDTS, fromTypedDomain.element, toTypedDomain.element, 
                                              excludeIDs=True, dts2=self.toDTS, ns2ns1Tbl=self.namespaceRenameTo))
            self.typedDomainsCorrespond[fromDimConcept, toDimConcept] = isCorresponding
            return isCorresponding


    def DRSdimsDiff(self, fromDTS, fromPriItemDRSrels, toDTS, toPriItemDRSrels):
        fromDims = {}
        toDims = {}
        for dts, priItemDRSrels, dims in ((fromDTS, fromPriItemDRSrels, fromDims), (toDTS, toPriItemDRSrels, toDims)):
            for dimRel, isNotAll, isClosed in self.DRSdimRels(dts, priItemDRSrels):
                dims[dimRel.toModelObject.qname, isNotAll] = dimRel
        diffs = []
        for i, fromDimKey in enumerate(fromDims.keys()):
            fromDimQname, fromIsNotAll = fromDimKey
            fromDimRel = fromDims[fromDimKey]
            fromDimConcept = fromDimRel.toModelObject
            toDimQname = self.toDTSqname(fromDimQname)
            toDimRel = toDims.get( (toDimQname, fromIsNotAll) )
            if toDimRel:
                toDimConcept = toDimRel.toModelObject
                mbrDiffs = self.DRSdiff(fromDimConcept, fromDimRel.consecutiveLinkrole,
                                        toDimConcept, toDimRel.consecutiveLinkrole,
                                        XbrlConst.dimensionDomain)
                dimsCorrespond = True
                if fromDimConcept.isTypedDimension: 
                    if toDimConcept.isExplicitDimension or self.typedDomainIsDifferent(fromDimConcept, toDimConcept):
                        dimsCorrespond = False
                elif toDimConcept.isTypedDimension:
                    dimsCorrespond = False
                if mbrDiffs or not dimsCorrespond:
                    diffs.append((fromDimRel, toDimRel, fromIsNotAll, mbrDiffs))
            else:
                diffs.append((fromDimRel, None, fromIsNotAll, []))
        for i, toDimKey in enumerate(toDims.keys()):
            toDimQname, toIsNotAll = toDimKey
            toDimRel = toDims[toDimKey]
            fromDimQname = self.fromDTSqname(toDimQname)
            if not fromDimQname or (fromDimQname, toIsNotAll) not in fromDims:
                toDimConcept = fromDimRel.toModelObject
                diffs.append((None, toDimRel, toIsNotAll, []))
        return diffs

    def toDTSqname(self, fromDTSqname):
        if fromDTSqname and fromDTSqname.namespaceURI in self.namespaceRenameFrom:
            # namespaceRenames dict's used for URIs, not objects, in report production
            NSrename = self.namespaceRenameFrom[fromDTSqname.namespaceURI]
            return qname(NSrename if isinstance(NSrename,str) else NSrename.toURI, 
                         fromDTSqname.localName)
        return fromDTSqname
        
    def fromDTSqname(self, toDTSqname):
        if toDTSqname and toDTSqname.namespaceURI in self.namespaceRenameTo:
            # namespaceRenames dict's used for URIs, not objects, in report production
            NSrename = self.namespaceRenameTo[toDTSqname.namespaceURI]
            return qname(NSrename if isinstance(NSrename,str) else NSrename.fromURI, 
                         toDTSqname.localName)
        return toDTSqname
        
    def createAction(self):
        action = XmlUtil.addChild(self.reportElement, XbrlConst.ver, "action", (("id","action{0:05}".format(self.actionNum) ),))
        self.actionNum += 1
        assignmentRef = XmlUtil.addChild(action, XbrlConst.ver, "assignmentRef", (("ref","versioningTask"),) )
        return action
    
    def createBaseEvent(self, eventName, fromURI, toURI):
        event = XmlUtil.addChild(self.createAction(), XbrlConst.ver, eventName)
        XmlUtil.addChild(event, XbrlConst.ver, "fromURI", ("value",fromURI))
        XmlUtil.addChild(event, XbrlConst.ver, "toURI", ("value",toURI))
    
    def createConceptEvent(self, eventNS, eventName, fromConcept=None, toConcept=None, action=None, fromCustomAttribute=None, toCustomAttribute=None, fromResource=None, toResource=None, fromValue=None, toValue=None, fromResourceText=None, toResourceText=None):
        if not action:
            action = self.createAction()
        event = XmlUtil.addChild(action, eventNS, eventName)
        if fromConcept:
            fromQname = XmlUtil.addQnameValue(self.reportElement, fromConcept.qname)
            fromElt = XmlUtil.addChild(event, XbrlConst.vercb, "vercb:fromConcept", ("name", fromQname) )
        if fromValue:
            XmlUtil.addComment(event, _("from value: {0} ").format(fromValue))
        if fromResource:
            fromResElt = XmlUtil.addChild(event, XbrlConst.verce, "verce:fromResource", ("value",self.conceptHref(fromResource)) )
            if fromResource.id is None and fromConcept:
                XmlUtil.addComment(event, _("({0} does not have an id attribute)").format(eventName))
            if fromResourceText:
                XmlUtil.addComment(event, fromResourceText)
        if fromCustomAttribute:
            if fromCustomAttribute.namespaceURI:  # has namespace
                attQname = XmlUtil.addQnameValue(self.reportElement, fromCustomAttribute)
                XmlUtil.addChild(event, XbrlConst.verce, "verce:fromCustomAttribute", (("name",attQname),) )
            else: # no namespace
                XmlUtil.addChild(event, XbrlConst.verce, "verce:fromCustomAttribute", (("name",fromCustomAttribute.localName),) )
        if toConcept:
            toQname = XmlUtil.addQnameValue(self.reportElement, toConcept.qname)
            toElt = XmlUtil.addChild(event, XbrlConst.vercb, "vercb:toConcept", ("name", toQname) )
        if toValue:
            XmlUtil.addComment(event, _("to value: {0} ").format(toValue))
        if toResource:
            toResElt = XmlUtil.addChild(event, XbrlConst.verce, "verce:toResource", ("value",self.conceptHref(toResource)) )
            if toResource.id is None and toConcept:
                XmlUtil.addComment(event, _("({0} does not have an id attribute)").format(eventName))
            if toResourceText:
                XmlUtil.addComment(event, toResourceText)
        if toCustomAttribute:
            if toCustomAttribute.namespaceURI:  # has namespace
                attQname = XmlUtil.addQnameValue(self.reportElement, toCustomAttribute)
                XmlUtil.addChild(event, XbrlConst.verce, "verce:toCustomAttribute", (("name",attQname),) )
            else: # no namespace
                XmlUtil.addChild(event, XbrlConst.verce, "verce:toCustomAttribute", (("name",toCustomAttribute.localName),) )
            
        return action
            
    def conceptHref(self, concept):
        conceptId = concept.id
        return (self.relativeUri(concept.modelDocument.uri) + "#" + 
            (conceptId if conceptId else XmlUtil.elementFragmentIdentifier(concept.element)))  
        
    def createRelationshipSetEvent(self, eventName, linkrole=None, arcrole=None, fromConcept=None, toConcept=None, axis=None, attrValues=None, comment=None, eventParent=None):
        if not eventParent:
            eventParent = self.createAction()
        eventAttributes = []
        if linkrole:
            eventAttributes.append(("linkrole", linkrole))
        if arcrole:
            eventAttributes.append(("arcrole", arcrole))
        if fromConcept:
            eventAttributes.append(("fromName", XmlUtil.addQnameValue(self.reportElement, fromConcept.qname)))
        if toConcept:
            eventAttributes.append(("toName", XmlUtil.addQnameValue(self.reportElement, toConcept.qname)))
        if axis:
            eventAttributes.append(("axis", axis))
        eventElement = XmlUtil.addChild(eventParent, XbrlConst.verrels, "verrels:" + eventName, attributes=eventAttributes)
        if comment:
            XmlUtil.addComment(eventParent, ' ' + comment + ' ')
        if attrValues:
            XmlUtil.addComment(eventParent, ' ' + ', '.join("{0[0]}='{0[1]}'".format(a) for a in sorted(attrValues)) + ' ')
        return eventElement
        
    def createInstanceAspectsEvent(self, eventName, eventAttributes=None, comment=None, eventParent=None):
        if not eventParent:
            eventParent = self.createAction()
        eventElement = XmlUtil.addChild(eventParent, XbrlConst.veria, "veria:" + eventName, 
                attributes=tuple((name,
                                  (XmlUtil.addQnameValue(self.reportElement, val) if isinstance(val,QName) else val)
                                  ) for name, val in eventAttributes) if eventAttributes else None)
        if comment:
            XmlUtil.addComment(eventParent, ' ' + comment + ' ')
        return eventElement
